import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


_APP_DIR_NAME = "motoboys-webapp"
_CONFIG_FILENAME = "local_config.json"


@dataclass(frozen=True)
class LocalConfigPaths:
    data_dir: Path
    file_path: Path


def _default_data_dir() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / _APP_DIR_NAME

    xdg_data = os.getenv("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / _APP_DIR_NAME

    return Path.home() / ".local" / "share" / _APP_DIR_NAME


def build_paths() -> LocalConfigPaths:
    data_dir = _default_data_dir()
    return LocalConfigPaths(data_dir=data_dir, file_path=data_dir / _CONFIG_FILENAME)


class LocalConfigStore:
    def __init__(self, file_path: Path | None = None):
        paths = build_paths()
        self.file_path = file_path or paths.file_path

    def load(self) -> dict[str, Any]:
        if not self.file_path.exists():
            return {}

        raw = self.file_path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}

        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Invalid local config format: expected object")
        return data

    def save(self, data: dict[str, Any]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)

        with NamedTemporaryFile("w", encoding="utf-8", dir=str(self.file_path.parent), delete=False) as tmp:
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name

        Path(tmp_name).replace(self.file_path)

    def update(self, patch: dict[str, Any]) -> dict[str, Any]:
        current = self.load()
        merged = dict(current)
        for key, value in patch.items():
            merged[key] = value
        self.save(merged)
        return merged
