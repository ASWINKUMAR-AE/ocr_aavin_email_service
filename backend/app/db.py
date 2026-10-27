"""
Database persistence layer supporting PostgreSQL with connection pooling
and transparent fallback/compatibility with local SQLite.
"""

import logging
import os
import re
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

logger = logging.getLogger("ocr.database")

# Threaded connection pool for PostgreSQL
_pg_pool = None
_pg_initialized = False


def is_test_environment() -> bool:
    """Return True if running in automated test suite (e.g. pytest)."""
    return (
        os.getenv("USE_POSTGRES_TESTS", "0").lower() not in ("1", "true")
        and (
            "PYTEST_CURRENT_TEST" in os.environ
            or "pytest" in sys.modules
            or os.getenv("TESTING", "0").lower() in ("1", "true")
        )
    )


def get_db_config() -> dict:
    """Retrieve database connection settings from environment."""
    return {
        "host": os.getenv("DB_HOST", "").strip(),
        "port": int(os.getenv("DB_PORT", "5432")),
        "name": os.getenv("DB_NAME", "").strip(),
        "user": os.getenv("DB_USER", "").strip(),
        "password": os.getenv("DB_PASSWORD", ""),
        "type": os.getenv("DB_TYPE", "postgres" if os.getenv("DB_HOST") else "sqlite").strip().lower(),
    }


def is_postgres() -> bool:
    """Determine whether PostgreSQL should be used."""
    if is_test_environment():
        return False
    cfg = get_db_config()
    return bool(cfg["host"] and cfg["name"] and cfg["type"] == "postgres")


def get_pg_pool():
    """Lazy initialize and return PostgreSQL connection pool."""
    global _pg_pool, _pg_initialized
    if _pg_pool is None:
        try:
            import psycopg2.pool
            cfg = get_db_config()
            logger.info("Initializing PostgreSQL connection pool to %s:%s/%s", cfg["host"], cfg["port"], cfg["name"])
            _pg_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=cfg["host"],
                port=cfg["port"],
                dbname=cfg["name"],
                user=cfg["user"],
                password=cfg["password"],
                connect_timeout=10,
            )
            _pg_initialized = True
        except Exception as exc:
            cfg = get_db_config()
            logger.error("Failed to connect to PostgreSQL at %s:%s/%s: %s", cfg["host"], cfg["port"], cfg["name"], exc)
            raise RuntimeError(f"Database connection error: Could not connect to PostgreSQL ({exc.__class__.__name__})") from exc
    return _pg_pool


class DBAdapter:
    """
    Unified database execution adapter.
    Normalizes PostgreSQL and SQLite query syntax, parameter styles,
    and returns dict-like row access.
    """

    def __init__(self, conn, is_postgres_conn: bool = False):
        self.conn = conn
        self.is_postgres = is_postgres_conn
        if self.is_postgres:
            import psycopg2.extras
            self.cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        else:
            self.cursor = conn.cursor()

    def _translate_query(self, query: str) -> str:
        if not self.is_postgres:
            return query
        q = query.strip()
        # BEGIN and PRAGMA are handled natively or irrelevant in PostgreSQL
        if q.upper().startswith("BEGIN") or q.upper().startswith("PRAGMA"):
            return ""
        # SQLite UPSERT -> PostgreSQL ON CONFLICT
        if "INSERT OR REPLACE INTO documents" in q:
            q = "INSERT INTO documents (id, payload) VALUES (?, ?) ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload"
        # rowid -> seq
        q = re.sub(r"\browid\b", "seq", q, flags=re.IGNORECASE)
        # ? parameter style -> %s parameter style
        q = q.replace("?", "%s")
        return q

    def execute(self, query: str, params: Union[Tuple, List, None] = None):
        translated = self._translate_query(query)
        if not translated:
            return self
        if params is not None:
            self.cursor.execute(translated, params)
        else:
            self.cursor.execute(translated)
        return self

    def executemany(self, query: str, seq_of_params):
        translated = self._translate_query(query)
        if not translated:
            return self
        self.cursor.executemany(translated, seq_of_params)
        return self

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def fetchmany(self, size: Optional[int] = None):
        return self.cursor.fetchmany(size) if size is not None else self.cursor.fetchmany()

    @property
    def rowcount(self):
        return self.cursor.rowcount

    @property
    def lastrowid(self):
        return getattr(self.cursor, "lastrowid", None)

    def __iter__(self):
        return iter(self.cursor)

    def close(self):
        if self.is_postgres and self.cursor and not self.cursor.closed:
            self.cursor.close()


@contextmanager
def get_connection(data_dir: Optional[Path] = None):
    """
    Context manager yielding an active database connection adapter.
    Automatically commits on success and rolls back on exception.
    """
    if is_postgres():
        pool = get_pg_pool()
        conn = None
        try:
            conn = pool.getconn()
            if conn.closed != 0:
                conn = pool.getconn()
            adapter = DBAdapter(conn, is_postgres_conn=True)
            try:
                yield adapter
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                adapter.close()
        finally:
            if conn is not None:
                pool.putconn(conn)
    else:
        from app.config import DATA
        target_dir = data_dir or DATA
        target_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(target_dir / "studio.sqlite3", timeout=20) as db:
            db.row_factory = sqlite3.Row
            yield DBAdapter(db, is_postgres_conn=False)


def _create_schema(db):
    if db.is_postgres:
        db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                seq BIGSERIAL,
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            );
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_documents_seq ON documents (seq DESC);")

        db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                seq BIGSERIAL,
                id TEXT PRIMARY KEY,
                document_id TEXT,
                union_code TEXT NOT NULL,
                organization_name TEXT NOT NULL,
                address TEXT NOT NULL,
                report_date TEXT NOT NULL,
                shift TEXT NOT NULL,
                abstract_no TEXT,
                milk_total_litres TEXT NOT NULL,
                milk_total_packets INTEGER NOT NULL,
                milk_total_trays TEXT NOT NULL,
                curd_buttermilk_total_litres TEXT NOT NULL,
                curd_buttermilk_total_packets INTEGER NOT NULL,
                curd_buttermilk_total_trays TEXT NOT NULL,
                grand_total_litres TEXT NOT NULL,
                grand_total_packets INTEGER NOT NULL,
                grand_total_trays TEXT NOT NULL,
                raw_ocr_text TEXT NOT NULL,
                parsed_json TEXT NOT NULL,
                validation_status TEXT NOT NULL,
                validation_warnings TEXT NOT NULL,
                ocr_created_at TEXT NOT NULL,
                report_processed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                email_status TEXT NOT NULL,
                email_sent_at TEXT,
                approved_by TEXT,
                approved_at TEXT,
                CONSTRAINT uq_report_business_key UNIQUE (union_code, report_date, shift)
            );
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS report_items (
                seq BIGSERIAL,
                id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                item_no INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity_litres TEXT NOT NULL,
                quantity_packets INTEGER NOT NULL,
                quantity_trays TEXT NOT NULL,
                row_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS report_audit_logs (
                seq BIGSERIAL,
                id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS admin_sessions (
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_reports_date ON reports (report_date);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_reports_shift ON reports (shift);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_reports_val_status ON reports (validation_status);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_reports_email_status ON reports (email_status);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_report_items_report_id ON report_items (report_id);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_report_audit_report_id ON report_audit_logs (report_id);")
    else:
        db.execute("CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, payload TEXT NOT NULL);")
        db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                document_id TEXT,
                union_code TEXT NOT NULL,
                organization_name TEXT NOT NULL,
                address TEXT NOT NULL,
                report_date TEXT NOT NULL,
                shift TEXT NOT NULL,
                abstract_no TEXT,
                milk_total_litres TEXT NOT NULL,
                milk_total_packets INTEGER NOT NULL,
                milk_total_trays TEXT NOT NULL,
                curd_buttermilk_total_litres TEXT NOT NULL,
                curd_buttermilk_total_packets INTEGER NOT NULL,
                curd_buttermilk_total_trays TEXT NOT NULL,
                grand_total_litres TEXT NOT NULL,
                grand_total_packets INTEGER NOT NULL,
                grand_total_trays TEXT NOT NULL,
                raw_ocr_text TEXT NOT NULL,
                parsed_json TEXT NOT NULL,
                validation_status TEXT NOT NULL,
                validation_warnings TEXT NOT NULL,
                ocr_created_at TEXT NOT NULL,
                report_processed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                email_status TEXT NOT NULL,
                email_sent_at TEXT,
                approved_by TEXT,
                approved_at TEXT,
                CONSTRAINT uq_report_business_key UNIQUE (union_code, report_date, shift)
            );
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS report_items (
                id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                item_no INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity_litres TEXT NOT NULL,
                quantity_packets INTEGER NOT NULL,
                quantity_trays TEXT NOT NULL,
                row_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS report_audit_logs (
                id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS admin_sessions (
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_reports_date ON reports (report_date);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_reports_shift ON reports (shift);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_reports_val_status ON reports (validation_status);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_reports_email_status ON reports (email_status);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_report_items_report_id ON report_items (report_id);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_report_audit_report_id ON report_audit_logs (report_id);")


def initialize_all_tables(db=None, data_dir: Optional[Path] = None):
    """
    Create tables, constraints, and indexes across both subsystems (documents and reports).
    """
    if db is not None:
        _create_schema(db)
    else:
        with get_connection(data_dir=data_dir) as conn:
            _create_schema(conn)


def migrate_sqlite_if_needed(db=None, data_dir: Optional[Path] = None):
    """
    Safely import existing records from local SQLite to PostgreSQL if PostgreSQL has missing records.
    Ensures zero data loss during database upgrade.
    """
    if not is_postgres():
        return
    from app.config import DATA
    target_dir = data_dir or DATA
    sqlite_file = target_dir / "studio.sqlite3"
    if not sqlite_file.is_file():
        return

    try:
        s_conn = sqlite3.connect(sqlite_file)
        s_conn.row_factory = sqlite3.Row

        def _do_migration(target_db):
            s_tables = [r[0] for r in s_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if "documents" in s_tables:
                for row in s_conn.execute("SELECT id, payload FROM documents"):
                    target_db.execute(
                        "INSERT INTO documents (id, payload) VALUES (?, ?) ON CONFLICT (id) DO NOTHING",
                        (row["id"], row["payload"])
                    )
            if "admin_users" in s_tables:
                for row in s_conn.execute("SELECT id, username, password_hash, salt, created_at, updated_at FROM admin_users"):
                    target_db.execute(
                        "INSERT INTO admin_users (id, username, password_hash, salt, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (username) DO NOTHING",
                        (row["id"], row["username"], row["password_hash"], row["salt"], row["created_at"], row["updated_at"])
                    )
            if "reports" in s_tables:
                for row in s_conn.execute("SELECT * FROM reports"):
                    r = dict(row)
                    target_db.execute(
                        """
                        INSERT INTO reports (
                            id, document_id, union_code, organization_name, address, report_date, shift, abstract_no,
                            milk_total_litres, milk_total_packets, milk_total_trays,
                            curd_buttermilk_total_litres, curd_buttermilk_total_packets, curd_buttermilk_total_trays,
                            grand_total_litres, grand_total_packets, grand_total_trays,
                            raw_ocr_text, parsed_json, validation_status, validation_warnings,
                            ocr_created_at, report_processed_at, created_at, updated_at,
                            email_status, email_sent_at, approved_by, approved_at
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?,
                            ?, ?, ?,
                            ?, ?, ?,
                            ?, ?, ?, ?,
                            ?, ?, ?, ?,
                            ?, ?, ?, ?
                        ) ON CONFLICT (union_code, report_date, shift) DO NOTHING
                        """,
                        (
                            r["id"], r.get("document_id"), r["union_code"], r["organization_name"], r["address"],
                            r["report_date"], r["shift"], r.get("abstract_no"), r["milk_total_litres"],
                            r["milk_total_packets"], r["milk_total_trays"], r["curd_buttermilk_total_litres"],
                            r["curd_buttermilk_total_packets"], r["curd_buttermilk_total_trays"],
                            r["grand_total_litres"], r["grand_total_packets"], r["grand_total_trays"],
                            r["raw_ocr_text"], r["parsed_json"], r["validation_status"], r["validation_warnings"],
                            r["ocr_created_at"], r["report_processed_at"], r["created_at"], r["updated_at"],
                            r["email_status"], r.get("email_sent_at"), r.get("approved_by"), r.get("approved_at")
                        )
                    )

        if db is not None:
            _do_migration(db)
        else:
            with get_connection(data_dir=target_dir) as conn:
                _do_migration(conn)
        s_conn.close()
        logger.info("Successfully checked and migrated existing SQLite data into PostgreSQL.")
    except Exception as exc:
        logger.warning("Notice during SQLite to PostgreSQL sync: %s", exc)
