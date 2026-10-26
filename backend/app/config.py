import os
from pathlib import Path

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
            if k and k not in os.environ:
                os.environ[k] = v

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
REPORT_EMAIL_CC = [e.strip() for e in os.getenv('REPORT_EMAIL_CC', '').split(',') if e.strip()]
REPORT_EMAIL_BCC = [e.strip() for e in os.getenv('REPORT_EMAIL_BCC', '').split(',') if e.strip()]
REPORT_EMAIL_ENABLED = os.getenv('REPORT_EMAIL_ENABLED', 'false').lower() in ('true', '1', 'yes')
REPORT_TIMEZONE = os.getenv('REPORT_TIMEZONE', 'Asia/Kolkata').strip()


def safe_report_config():
    """Return reporting and email configuration without exposing secrets."""
    return {
        'smtp_configured': bool(SMTP_HOST and SMTP_FROM_EMAIL),
        'smtp_host': SMTP_HOST or None,
        'smtp_port': SMTP_PORT,
        'smtp_from_email': SMTP_FROM_EMAIL or None,
        'smtp_from_name': SMTP_FROM_NAME,
        'smtp_use_tls': SMTP_USE_TLS,
        'smtp_use_ssl': SMTP_USE_SSL,
        'report_email_enabled': REPORT_EMAIL_ENABLED,
        'report_email_to': REPORT_EMAIL_TO,
        'report_email_cc': REPORT_EMAIL_CC,
        'report_email_bcc': REPORT_EMAIL_BCC,
        'report_timezone': REPORT_TIMEZONE,
    }

