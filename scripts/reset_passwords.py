"""Reset UI passwords by updating a .env file.

Why: P5 goal is a practical "admin reset password" path without adding a full user table.
"""

from __future__ import annotations

import argparse
import secrets
from pathlib import Path


def _gen_password(nbytes: int = 18) -> str:
    return secrets.token_urlsafe(nbytes)


def _read_env_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines(keepends=False)


def _set_kv(lines: list[str], key: str, value: str) -> list[str]:
    out: list[str] = []
    found = False
    prefix = f"{key}="
    for ln in lines:
        if ln.startswith(prefix):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"{key}={value}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=".env", help="Path to .env to edit")
    ap.add_argument("--set-admin", default=None, help="Set ADMIN_PASSWORD to provided value")
    ap.add_argument("--set-cashier", default=None, help="Set CASHIER_PASSWORD to provided value")
    ap.add_argument("--rotate-admin", action="store_true", help="Generate a new ADMIN_PASSWORD")
    ap.add_argument("--rotate-cashier", action="store_true", help="Generate a new CASHIER_PASSWORD")
    ap.add_argument("--rotate-session", action="store_true", help="Generate a new SESSION_SECRET")
    ap.add_argument("--rotate-all", action="store_true", help="Rotate admin + cashier + session")
    args = ap.parse_args()

    env_path = Path(args.env).resolve()
    lines = _read_env_lines(env_path)

    rotate_admin = args.rotate_all or args.rotate_admin
    rotate_cashier = args.rotate_all or args.rotate_cashier
    rotate_session = args.rotate_all or args.rotate_session

    changes: dict[str, str] = {}
    if args.set_admin and rotate_admin:
        ap.error("Use either --set-admin or --rotate-admin (not both)")
    if args.set_cashier and rotate_cashier:
        ap.error("Use either --set-cashier or --rotate-cashier (not both)")

    if args.set_admin is not None:
        changes["ADMIN_PASSWORD"] = args.set_admin
    elif rotate_admin:
        changes["ADMIN_PASSWORD"] = _gen_password()

    if args.set_cashier is not None:
        changes["CASHIER_PASSWORD"] = args.set_cashier
    elif rotate_cashier:
        changes["CASHIER_PASSWORD"] = _gen_password()

    if rotate_session:
        changes["SESSION_SECRET"] = _gen_password()

    if not changes:
        ap.error("Nothing to do. Use --rotate-admin/--rotate-all or --set-admin etc.")

    for k, v in changes.items():
        lines = _set_kv(lines, k, v)

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Updated: {env_path}")
    for k, v in changes.items():
        if k.endswith("PASSWORD"):
            print(f"{k}={v}")
        else:
            print(f"{k}=<rotated>")

    print("\nRestart containers to apply env changes:\n  docker compose up -d")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
