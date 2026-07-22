"""
Configuration layer.

Design pattern: Singleton — exactly one ConfigManager instance exists per
test process, so every fixture/page/util reads identical, already-resolved
config instead of re-parsing YAML hundreds of times across a 10k-test suite.

Resolution order (highest wins):
    1. Real OS environment variables (CI secrets, `export FOO=bar`)
    2. Values in .env (local dev convenience, loaded via python-dotenv)
    3. environments.yaml for the active TEST_ENV block

This means a GitHub Actions secret can always override a checked-in YAML
default without editing code.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_YAML_PATH = _REPO_ROOT / "config" / "environments.yaml"

# Keys whose values must never be printed/logged verbatim.
_SENSITIVE_KEYS = {
    "password",
    "app_password",
    "api_token",
    "api_client_secret",
    "db_password",
    "vault_token",
    "secret",
}


def _mask(key: str, value: Any) -> Any:
    if value and any(s in key.lower() for s in _SENSITIVE_KEYS):
        return "***MASKED***"
    return value


@dataclass(frozen=True)
class DBConfig:
    host: str
    port: int
    name: str
    driver: str
    user: str = ""
    password: str = ""


@dataclass(frozen=True)
class Config:
    env_name: str
    browser: str
    headless: bool
    viewport: dict[str, int]
    timeout_ms: int
    navigation_timeout_ms: int
    retries: int
    screenshot_on_failure: bool
    video_on_failure: bool
    trace_on_failure: bool
    slow_mo_ms: int
    base_url: str
    api_base_url: str
    db: DBConfig
    app_username: str = ""
    app_password: str = ""
    api_token: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def safe_dict(self) -> dict[str, Any]:
        """Representation safe to print/log — secrets masked."""
        raw = {
            "env_name": self.env_name,
            "browser": self.browser,
            "headless": self.headless,
            "base_url": self.base_url,
            "api_base_url": self.api_base_url,
            "app_username": self.app_username,
            "app_password": self.app_password,
            "api_token": self.api_token,
            "db_host": self.db.host,
            "db_password": self.db.password,
        }
        return {k: _mask(k, v) for k, v in raw.items()}


class ConfigManager:
    """Thread-safe singleton. Use ConfigManager.get() everywhere."""

    _instance: "ConfigManager | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "ConfigManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._config = None  # type: ignore[attr-defined]
        return cls._instance

    @classmethod
    def get(cls, force_reload: bool = False) -> Config:
        instance = cls()
        if instance._config is None or force_reload:  # type: ignore[attr-defined]
            instance._config = instance._load()  # type: ignore[attr-defined]
        return instance._config  # type: ignore[attr-defined]

    @staticmethod
    def _load() -> Config:
        load_dotenv(_REPO_ROOT / ".env", override=False)

        env_name = os.getenv("TEST_ENV", "qa")

        if not _ENV_YAML_PATH.exists():
            raise FileNotFoundError(f"Missing config file: {_ENV_YAML_PATH}")

        with open(_ENV_YAML_PATH, "r", encoding="utf-8") as f:
            all_envs = yaml.safe_load(f)

        if env_name not in all_envs:
            raise ValueError(
                f"Unknown TEST_ENV '{env_name}'. Available: {list(all_envs.keys())}"
            )

        block = all_envs[env_name]

        db_block = block.get("db", {})
        db = DBConfig(
            host=db_block.get("host", ""),
            port=int(db_block.get("port", 5432)),
            name=db_block.get("name", ""),
            driver=db_block.get("driver", "postgresql"),
            user=os.getenv("DB_USER", ""),
            password=os.getenv("DB_PASSWORD", ""),
        )

        return Config(
            env_name=env_name,
            browser=os.getenv("BROWSER", block.get("browser", "chromium")),
            headless=_env_bool("HEADLESS", block.get("headless", True)),
            viewport=block.get("viewport", {"width": 1920, "height": 1080}),
            timeout_ms=int(block.get("timeout_ms", 30000)),
            navigation_timeout_ms=int(block.get("navigation_timeout_ms", 45000)),
            retries=int(os.getenv("RETRIES", block.get("retries", 0))),
            screenshot_on_failure=bool(block.get("screenshot_on_failure", True)),
            video_on_failure=bool(block.get("video_on_failure", True)),
            trace_on_failure=bool(block.get("trace_on_failure", True)),
            slow_mo_ms=int(block.get("slow_mo_ms", 0)),
            base_url=os.getenv("BASE_URL", block.get("base_url", "")),
            api_base_url=os.getenv("API_BASE_URL", block.get("api_base_url", "")),
            db=db,
            app_username=os.getenv("APP_USERNAME", ""),
            app_password=os.getenv("APP_PASSWORD", ""),
            api_token=os.getenv("API_TOKEN", ""),
        )


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def get_config(force_reload: bool = False) -> Config:
    """Convenience module-level accessor."""
    return ConfigManager.get(force_reload=force_reload)
