import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from typing import Any

from app.core.local_config import LocalConfigStore


PBKDF2_ITERATIONS = 310_000


@dataclass(frozen=True)
class Credential:
    username: str
    password_hash: str


@dataclass(frozen=True)
class AuthDefaults:
    admin_username: str
    admin_password: str
    cashier_username: str
    cashier_password: str


class AuthProvider:
    def __init__(self, *, desktop_mode: bool, defaults: AuthDefaults, local_config_store: LocalConfigStore | None = None):
        self.desktop_mode = desktop_mode
        self.defaults = defaults
        self.local_config_store = local_config_store or LocalConfigStore()

    def _hash_password(self, plain_password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"

    def _verify_hash(self, plain_password: str, encoded_hash: str) -> bool:
        try:
            algo, iter_raw, salt_hex, hash_hex = encoded_hash.split("$", 3)
            if algo != "pbkdf2_sha256":
                return False
            iterations = int(iter_raw)
            salt = bytes.fromhex(salt_hex)
        except (ValueError, TypeError):
            return False

        digest = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(digest.hex(), hash_hex)

    def _load_local_credentials(self) -> dict[str, Credential]:
        data = self.local_config_store.load()
        creds: dict[str, Credential] = {}
        for role in ("ADMIN", "CASHIER"):
            role_data: dict[str, Any] = (data.get("credentials") or {}).get(role, {})
            username = str(role_data.get("username") or "").strip()
            password_hash = str(role_data.get("password_hash") or "").strip()
            if username and password_hash:
                creds[role] = Credential(username=username, password_hash=password_hash)
        return creds

    def needs_initial_setup(self) -> bool:
        if not self.desktop_mode:
            return False
        creds = self._load_local_credentials()
        return "ADMIN" not in creds or "CASHIER" not in creds

    def verify_credentials(self, username: str, password: str) -> str | None:
        u = username.strip()

        if self.desktop_mode:
            if self.needs_initial_setup():
                return None
            local_creds = self._load_local_credentials()
            for role in ("ADMIN", "CASHIER"):
                c = local_creds.get(role)
                if not c:
                    continue
                if hmac.compare_digest(u, c.username) and self._verify_hash(password, c.password_hash):
                    return role
            return None

        if hmac.compare_digest(u, self.defaults.admin_username) and hmac.compare_digest(password, self.defaults.admin_password):
            return "ADMIN"
        if hmac.compare_digest(u, self.defaults.cashier_username) and hmac.compare_digest(password, self.defaults.cashier_password):
            return "CASHIER"
        return None

    def save_initial_credentials(
        self,
        *,
        admin_username: str,
        admin_password: str,
        cashier_username: str,
        cashier_password: str,
        sensitive_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.desktop_mode:
            raise RuntimeError("Initial setup is only supported in desktop mode")

        payload = {
            "credentials": {
                "ADMIN": {
                    "username": admin_username.strip(),
                    "password_hash": self._hash_password(admin_password),
                },
                "CASHIER": {
                    "username": cashier_username.strip(),
                    "password_hash": self._hash_password(cashier_password),
                },
            },
            "initial_setup_completed": True,
        }
        if sensitive_config is not None:
            payload["sensitive_config"] = sensitive_config

        self.local_config_store.save(payload)
        return payload


def build_auth_provider(*, app_env: str) -> AuthProvider:
    desktop_mode = app_env == "desktop" or os.getenv("DESKTOP_MODE", "").strip().lower() in {"1", "true", "yes"}
    defaults = AuthDefaults(
        admin_username=os.getenv("ADMIN_USERNAME", "admin").strip() or "admin",
        admin_password=os.getenv("ADMIN_PASSWORD", "admin").strip() or "admin",
        cashier_username=os.getenv("CASHIER_USERNAME", "caixa").strip() or "caixa",
        cashier_password=os.getenv("CASHIER_PASSWORD", "caixa").strip() or "caixa",
    )
    return AuthProvider(desktop_mode=desktop_mode, defaults=defaults)
