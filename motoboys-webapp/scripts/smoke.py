import datetime as dt
import json
import time
import urllib.error
import urllib.request
from argparse import ArgumentParser
import sys
from pathlib import Path

from sqlalchemy import text as sa_text


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = ArgumentParser(description="Smoke check para DB e endpoint de saúde")
    parser.add_argument("--health-url", help="URL do endpoint de saúde para validar via HTTP")
    parser.add_argument("--health-timeout", type=float, default=3.0, help="timeout por requisição HTTP")
    parser.add_argument("--health-retries", type=int, default=20, help="tentativas para o healthcheck HTTP")
    parser.add_argument("--health-sleep", type=float, default=1.0, help="intervalo entre tentativas do healthcheck")
    args = parser.parse_args()

    import app.main  # noqa: F401

    from app.db import SessionLocal
    from app.services.week_service import get_current_week

    db = SessionLocal()
    try:
        db.execute(sa_text("SELECT 1"))
        w = get_current_week(db, dt.date.today())
        print(f"SMOKE_DB_OK week_id={w.id} status={w.status}")
    finally:
        db.close()

    if args.health_url:
        for attempt in range(1, args.health_retries + 1):
            try:
                with urllib.request.urlopen(args.health_url, timeout=args.health_timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
                    if response.status != 200 or body.get("ok") is not True:
                        raise RuntimeError(f"Resposta inválida de healthcheck: status={response.status} body={body}")
                print(f"SMOKE_HEALTH_OK url={args.health_url} attempts={attempt}")
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
                if attempt == args.health_retries:
                    raise RuntimeError(f"Healthcheck falhou em {args.health_url} após {attempt} tentativas") from exc
                time.sleep(args.health_sleep)


if __name__ == "__main__":
    main()
