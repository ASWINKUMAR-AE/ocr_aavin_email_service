#!/usr/bin/env python3
"""
Production Entrypoint for Aavin OCR Email Automation Service.
Binds to configured HOST (default 0.0.0.0) and PORT (default 8000),
supports environment variables, CLI options, and clean graceful shutdowns.
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure ROOT and backend directory are in sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'backend'))

# Enforce offline Paddle / HuggingFace runtime mode
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_DISABLE_XET'] = '1'

# Load optional .env file if available
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
            if k not in os.environ:
                os.environ[k] = v


def main():
    parser = argparse.ArgumentParser(description="Aavin OCR Email Automation Service")
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host interface to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Port number to listen on (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("RELOAD", "false").lower() in ("true", "1"),
        help="Enable auto-reload on code change (development only)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.getenv("WORKERS", "1")),
        help="Number of uvicorn worker processes (default: 1)"
    )

    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "app.main:app",
        app_dir=str(ROOT / "backend"),
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
        access_log=False,
    )


if __name__ == "__main__":
    main()
