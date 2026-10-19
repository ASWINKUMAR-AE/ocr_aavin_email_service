import subprocess
import sys
from pathlib import Path


def test_offline_guard_blocks_outbound_connections():
    # Separate process: audit hooks cannot be removed from a pytest process.
    code = """
from app.runtime import configure_offline_runtime
import socket
configure_offline_runtime()
try:
    socket.socket().connect(('203.0.113.1', 443))
except OSError as error:
    assert 'Outbound network disabled' in str(error)
else:
    raise AssertionError('Connection not blocked')
"""
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run([sys.executable, '-c', code], cwd=root, capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stderr
