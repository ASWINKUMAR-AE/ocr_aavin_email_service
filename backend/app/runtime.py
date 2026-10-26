"""Keep runtime caches local and reject outbound Python socket connections.

PaddleX 3.3.10 probes model hosts during import even with explicit model dirs.
Its newer DISABLE_MODEL_SOURCE_CHECK flag does not exist in this pinned release.
The audit guard fails those probes locally. Installation runs in a separate process.
"""
import os
import sys
from app import config
from app.config import ROOT

_configured = False


def configure_offline_runtime():
    global _configured
    if _configured:
        return
    os.environ.setdefault('PADDLE_PDX_CACHE_HOME', str(ROOT / '.cache/paddlex'))
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'

    def guard(event, args):
        if event == 'socket.connect':
            address = args[1]
            if isinstance(address, tuple):
                host = address[0]
                port = address[1] if len(address) > 1 else None
                # Allow loopback connections
                if host in ('127.0.0.1', '::1', 'localhost'):
                    return
                # Allow outbound SMTP email dispatch
                if config.REPORT_EMAIL_ENABLED and port in (config.SMTP_PORT, 587, 465, 25, 2525):
                    return
                raise OSError('Outbound network disabled in local OCR runtime')

    sys.addaudithook(guard)
    _configured = True
