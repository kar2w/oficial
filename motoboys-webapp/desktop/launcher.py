from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

APP_NAME = "Motoboys WebApp"
APP_VERSION = "1.0.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_START_PORT = 8000


def _find_free_port(start_port: int = DEFAULT_START_PORT) -> int:
    for port in range(start_port, start_port + 1000):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex((DEFAULT_HOST, port)) != 0:
                return port
    raise RuntimeError("Não foi possível encontrar uma porta livre.")


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[1]


def _user_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "MotoboysWebApp"


def _prepare_runtime_env(project_root: Path) -> tuple[dict[str, str], Path, Path]:
    env = os.environ.copy()
    data_dir = _user_data_dir()
    logs_dir = data_dir / "logs"
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    weekly_file = data_dir / "entregadores_semanais.json"
    bundled_weekly = project_root / "data" / "entregadores_semanais.json"
    if bundled_weekly.exists() and not weekly_file.exists():
        weekly_file.write_bytes(bundled_weekly.read_bytes())

    env.setdefault("APP_ENV", "prod")
    env.setdefault("TZ", "America/Fortaleza")
    env.setdefault("USER_DATA_DIR", str(data_dir))
    env.setdefault("LOG_DIR", str(logs_dir))
    env.setdefault("WEEKLY_COURIERS_JSON_PATH", str(weekly_file if weekly_file.exists() else bundled_weekly))

    # Defaults de desktop (sobrescreva por variáveis de ambiente para produção).
    env.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/motoboys")
    env.setdefault("SESSION_SECRET", "desktop-secret-change-me")
    env.setdefault("ADMIN_USERNAME", "admin")
    env.setdefault("ADMIN_PASSWORD", "admin")
    env.setdefault("CASHIER_USERNAME", "caixa")
    env.setdefault("CASHIER_PASSWORD", "caixa")

    pythonpath_parts = [str(project_root)]
    current_pythonpath = env.get("PYTHONPATH", "").strip()
    if current_pythonpath:
        pythonpath_parts.append(current_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    return env, data_dir, logs_dir


def _wait_for_server(url: str, timeout_s: float = 20.0) -> bool:
    import urllib.request

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:  # nosec B310
                if response.status < 500:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def main() -> int:
    root = _project_root()
    env, _, logs_dir = _prepare_runtime_env(root)
    port = _find_free_port()

    log_file = logs_dir / "desktop-launcher.log"
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando {APP_NAME} v{APP_VERSION} na porta {port}\n")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        DEFAULT_HOST,
        "--port",
        str(port),
    ]

    server = subprocess.Popen(cmd, cwd=str(root), env=env)  # noqa: S603
    login_url = f"http://{DEFAULT_HOST}:{port}/ui/login"

    try:
        if _wait_for_server(f"http://{DEFAULT_HOST}:{port}/health"):
            webbrowser.open(login_url)
        else:
            with log_file.open("a", encoding="utf-8") as handle:
                handle.write("Servidor não respondeu no tempo esperado.\n")
        return server.wait()
    except KeyboardInterrupt:
        server.terminate()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
