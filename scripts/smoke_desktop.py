#!/usr/bin/env python3
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import psycopg


def _to_psycopg_dsn(sqlalchemy_url: str) -> str:
    return sqlalchemy_url.replace("+psycopg", "", 1)


def _wait_http_ok(url: str, retries: int, sleep_s: float, allowed_statuses: set[int]) -> int:
    for attempt in range(1, retries + 1):
        try:
            with urlopen(url, timeout=5) as resp:
                if resp.status in allowed_statuses:
                    return attempt
        except URLError:
            pass
        time.sleep(sleep_s)
    raise RuntimeError(f"URL não respondeu status esperado: {url}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke desktop (DB init + boot + /health + UI)")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--schema", default="db/schema.sql")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--health-url", default="http://127.0.0.1:8000/health")
    parser.add_argument("--ui-url", default="http://127.0.0.1:8000/ui/login")
    parser.add_argument("--retries", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=1.0)
    args = parser.parse_args()

    if not args.database_url:
        raise RuntimeError("DATABASE_URL obrigatório para smoke desktop")

    schema_sql = Path(args.schema).read_text(encoding="utf-8")
    dsn = _to_psycopg_dsn(args.database_url)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
            cur.execute("SELECT 1")

    env = os.environ.copy()
    env.setdefault("DATABASE_URL", args.database_url)
    env.setdefault("SESSION_SECRET", "smoke-session-secret")
    env.setdefault("ADMIN_USERNAME", "admin")
    env.setdefault("ADMIN_PASSWORD", "admin")

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "--app-dir",
            "motoboys-webapp",
            "app.main:app",
            "--host",
            args.host,
            "--port",
            str(args.port),
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        health_attempt = _wait_http_ok(args.health_url, args.retries, args.sleep, {200})
        ui_attempt = _wait_http_ok(args.ui_url, args.retries, args.sleep, {200})
        print(f"SMOKE_DESKTOP_OK health_attempt={health_attempt} ui_attempt={ui_attempt}")
        return 0
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
