import json
import os
from pathlib import Path
from typing import Any, Dict, List, Union

ROOT = Path(__file__).resolve().parents[2]
# Load optional .env file from project root
env_path = ROOT / '.env'
if env_path.is_file():
    with env_path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip().strip("'\"")
DATA = Path(os.getenv('OCR_DATA_DIR', ROOT / 'data')).resolve()
MODELS = Path(os.getenv('OCR_MODEL_DIR', ROOT / 'models')).resolve()
MAX_UPLOAD = int(os.getenv('OCR_MAX_UPLOAD_MB', '25')) * 1024 * 1024
MAX_PAGES = int(os.getenv('OCR_MAX_PAGES', '10'))
MAX_PIXELS = int(os.getenv('OCR_MAX_PIXELS', '24000000'))
MAX_SIDE = int(os.getenv('OCR_MAX_SIDE', '2000'))
PDF_DPI = int(os.getenv('OCR_PDF_DPI', '150'))
CPU_THREADS = int(os.getenv('OCR_CPU_THREADS', '4'))
DETECTOR = 'PP-OCRv5_mobile_det'
RECOGNIZER = 'ta_PP-OCRv5_mobile_rec'

# SMTP & Report Configuration
SMTP_HOST = ''
SMTP_PORT = 587
SMTP_USER = ''
SMTP_PASSWORD = ''
SMTP_FROM_EMAIL = 'reports@aavin.local'
SMTP_FROM_NAME = 'Aavin OCR Reports'
SMTP_USE_TLS = True
SMTP_USE_SSL = False
REPORT_EMAIL_TO = ['reports@aavin.local']
REPORT_RECIPIENT_PREFERENCES = [
    {'email': 'reports@aavin.local', 'send_pdf': True, 'send_excel': False}
]
REPORT_EMAIL_CC = []
REPORT_EMAIL_BCC = []
REPORT_EMAIL_ENABLED = False
REPORT_TIMEZONE = 'Asia/Kolkata'


def reload_env():
    """Reload environment and report config from .env."""
    global SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL, SMTP_FROM_NAME
    global SMTP_USE_TLS, SMTP_USE_SSL, REPORT_EMAIL_TO, REPORT_RECIPIENT_PREFERENCES
    global REPORT_EMAIL_CC, REPORT_EMAIL_BCC, REPORT_EMAIL_ENABLED, REPORT_TIMEZONE

    if env_path.is_file():
        with env_path.open('r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip().strip("'\"")

    SMTP_HOST = os.getenv('SMTP_HOST', '').strip()
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER = os.getenv('SMTP_USER', '').strip()
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL', 'reports@aavin.local').strip()
    SMTP_FROM_NAME = os.getenv('SMTP_FROM_NAME', 'Aavin OCR Reports').strip()
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'true').lower() in ('true', '1', 'yes')
    SMTP_USE_SSL = os.getenv('SMTP_USE_SSL', 'false').lower() in ('true', '1', 'yes')

    raw_to = os.getenv('REPORT_EMAIL_TO', '').strip()
    REPORT_EMAIL_TO = [e.strip() for e in raw_to.split(',') if e.strip()] if raw_to else ['reports@aavin.local']

    raw_prefs = os.getenv('REPORT_RECIPIENT_PREFERENCES', '').strip()
    parsed_prefs = []
    if raw_prefs:
        try:
            items = json.loads(raw_prefs)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and 'email' in item and item['email'].strip():
                        parsed_prefs.append({
                            'role': str(item.get('role', 'STAFF')).strip().upper(),
                            'name': str(item.get('name', '')).strip(),
                            'email': item['email'].strip(),
                            'send_pdf': bool(item.get('send_pdf', True)),
                            'send_excel': bool(item.get('send_excel', False)),
                        })
        except Exception:
            parsed_prefs = []

    if parsed_prefs:
        REPORT_RECIPIENT_PREFERENCES = parsed_prefs
        REPORT_EMAIL_TO = [p['email'] for p in parsed_prefs]
    else:
        # Default with GM, AGM, AA role structure
        default_roles = ['GM', 'AGM', 'AA']
        role_names = {
            'GM': 'General Manager',
            'AGM': 'Asst. General Manager',
            'AA': 'Administrative Assistant / Accounts'
        }
        recs = []
        for idx, e in enumerate(REPORT_EMAIL_TO):
            r_role = default_roles[idx] if idx < len(default_roles) else 'STAFF'
            recs.append({
                'role': r_role,
                'name': role_names.get(r_role, 'Staff Recipient'),
                'email': e,
                'send_pdf': True,
                'send_excel': (r_role == 'AGM')
            })
        if len(recs) < 3:
            recs.append({
                'role': 'AA',
                'name': 'Administrative Assistant / Accounts',
                'email': 'aa.aavin@gmail.com',
                'send_pdf': True,
                'send_excel': False
            })
        REPORT_RECIPIENT_PREFERENCES = recs

    REPORT_EMAIL_CC = [e.strip() for e in os.getenv('REPORT_EMAIL_CC', '').split(',') if e.strip()]
    REPORT_EMAIL_BCC = [e.strip() for e in os.getenv('REPORT_EMAIL_BCC', '').split(',') if e.strip()]
    REPORT_EMAIL_ENABLED = os.getenv('REPORT_EMAIL_ENABLED', 'false').lower() in ('true', '1', 'yes')
    REPORT_TIMEZONE = os.getenv('REPORT_TIMEZONE', 'Asia/Kolkata').strip()


reload_env()


def safe_report_config():
    """Return reporting and email configuration without exposing secrets."""
    reload_env()
    return {
        'smtp_configured': bool(SMTP_HOST and SMTP_FROM_EMAIL),
        'smtp_host': SMTP_HOST or 'smtp.gmail.com',
        'smtp_port': SMTP_PORT,
        'smtp_user': SMTP_USER or None,
        'smtp_password_set': bool(SMTP_PASSWORD),
        'smtp_from_email': SMTP_FROM_EMAIL or None,
        'smtp_from_name': SMTP_FROM_NAME or 'Aavin OCR Reports',
        'smtp_use_tls': SMTP_USE_TLS,
        'smtp_use_ssl': SMTP_USE_SSL,
        'report_email_enabled': REPORT_EMAIL_ENABLED,
        'report_email_to': REPORT_EMAIL_TO,
        'report_recipients': REPORT_RECIPIENT_PREFERENCES,
        'report_email_cc': REPORT_EMAIL_CC,
        'report_email_bcc': REPORT_EMAIL_BCC,
        'report_timezone': REPORT_TIMEZONE,
    }


def update_sender_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update SMTP sender settings (email, app password, host, port, etc.) in .env and runtime config.
    """
    global SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL, SMTP_FROM_NAME, SMTP_USE_TLS, SMTP_USE_SSL

    new_host = str(settings.get('smtp_host') or SMTP_HOST or 'smtp.gmail.com').strip()
    new_port = str(settings.get('smtp_port') or SMTP_PORT or 587).strip()
    new_user = str(settings.get('smtp_user') if settings.get('smtp_user') is not None else SMTP_USER).strip()
    
    # Only update password if non-empty string provided
    new_pass = settings.get('smtp_password')
    if new_pass is not None and str(new_pass).strip():
        actual_pass = str(new_pass).strip()
    else:
        actual_pass = SMTP_PASSWORD

    new_from_email = str(settings.get('smtp_from_email') or new_user or SMTP_FROM_EMAIL).strip()
    new_from_name = str(settings.get('smtp_from_name') or SMTP_FROM_NAME or 'Aavin OCR Reports').strip()
    new_tls = 'true' if settings.get('smtp_use_tls', True) else 'false'
    new_ssl = 'true' if settings.get('smtp_use_ssl', False) else 'false'

    updates = {
        'SMTP_HOST': new_host,
        'SMTP_PORT': new_port,
        'SMTP_USER': new_user,
        'SMTP_PASSWORD': actual_pass,
        'SMTP_FROM_EMAIL': new_from_email,
        'SMTP_FROM_NAME': new_from_name,
        'SMTP_USE_TLS': new_tls,
        'SMTP_USE_SSL': new_ssl,
        'REPORT_EMAIL_ENABLED': 'true' if (new_host and new_from_email) else 'false'
    }

    lines = []
    keys_found = set()
    if env_path.is_file():
        with env_path.open('r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                replaced = False
                for k, v in updates.items():
                    if stripped.startswith(f"{k}=") or stripped.startswith(f"{k} ="):
                        lines.append(f"{k}={v}\n")
                        keys_found.add(k)
                        replaced = True
                        break
                if not replaced:
                    lines.append(line)

    for k, v in updates.items():
        if k not in keys_found:
            lines.append(f"{k}={v}\n")

    with env_path.open('w', encoding='utf-8') as f:
        f.writelines(lines)

    reload_env()
    return safe_report_config()


def update_report_recipients(new_recipients: List[Union[Dict[str, Any], str]]) -> List[Dict[str, Any]]:
    """
    Update recipients, designations (GM, AGM, AA), and delivery preferences in .env.
    """
    global REPORT_EMAIL_TO, REPORT_RECIPIENT_PREFERENCES
    cleaned: List[Dict[str, Any]] = []
    seen = set()

    for item in new_recipients:
        if isinstance(item, str):
            email = item.strip()
            role = 'STAFF'
            name = ''
            send_pdf = True
            send_excel = False
        elif isinstance(item, dict):
            email = str(item.get('email', '')).strip()
            role = str(item.get('role', 'STAFF')).strip().upper()
            name = str(item.get('name', '')).strip()
            send_pdf = bool(item.get('send_pdf', False))
            send_excel = bool(item.get('send_excel', False))
        else:
            continue

        if email and email not in seen:
            seen.add(email)
            cleaned.append({
                'role': role or 'STAFF',
                'name': name,
                'email': email,
                'send_pdf': send_pdf,
                'send_excel': send_excel
            })

    if not cleaned:
        raise ValueError("At least one recipient email address is required.")

    val_to = ",".join(c['email'] for c in cleaned)
    val_prefs = json.dumps(cleaned)

    lines = []
    found_to = False
    found_prefs = False
    if env_path.is_file():
        with env_path.open('r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith('REPORT_EMAIL_TO=') or stripped.startswith('REPORT_EMAIL_TO ='):
                    lines.append(f"REPORT_EMAIL_TO={val_to}\n")
                    found_to = True
                elif stripped.startswith('REPORT_RECIPIENT_PREFERENCES=') or stripped.startswith('REPORT_RECIPIENT_PREFERENCES ='):
                    lines.append(f"REPORT_RECIPIENT_PREFERENCES={val_prefs}\n")
                    found_prefs = True
                else:
                    lines.append(line)
    if not found_to:
        lines.append(f"REPORT_EMAIL_TO={val_to}\n")
    if not found_prefs:
        lines.append(f"REPORT_RECIPIENT_PREFERENCES={val_prefs}\n")

    with env_path.open('w', encoding='utf-8') as f:
        f.writelines(lines)

    reload_env()
    return REPORT_RECIPIENT_PREFERENCES


