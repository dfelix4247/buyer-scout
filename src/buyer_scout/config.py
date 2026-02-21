from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_DB_PATH = Path("C:/Users/danie/dev/scout-data/scout.db")
DEFAULT_AUTH_PATH = Path("C:/Users/danie/dev/scout-data/buyer-scout/auth.json")
DEFAULT_DEBUG_DIR = Path("C:/Users/danie/dev/scout-data/buyer-scout/debug")
DEFAULT_ENV_PATH = Path("C:/Users/danie/dev/scout-data/.env")


@dataclass(slots=True)
class AppConfig:
    db_path: Path
    auth_path: Path
    debug_dir: Path


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_shared_env() -> None:
    """
    Load shared dotenv file for local development.

    Precedence:
      1) SCOUT_ENV_PATH if set
      2) DEFAULT_ENV_PATH (C:/Users/danie/dev/scout-data/.env)

    Does NOT override already-set environment variables.
    Safe to call multiple times.
    """
    env_override = os.getenv("SCOUT_ENV_PATH")
    env_path = Path(env_override) if env_override else DEFAULT_ENV_PATH

    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


def get_config() -> AppConfig:
    # Ensure dotenv is loaded before reading env vars
    load_shared_env()

    db_path = Path(os.getenv("SCOUT_DB_PATH", str(DEFAULT_DB_PATH)))
    auth_path = Path(os.getenv("BUYER_SCOUT_AUTH_PATH", str(DEFAULT_AUTH_PATH)))
    debug_dir = Path(os.getenv("BUYER_SCOUT_DEBUG_DIR", str(DEFAULT_DEBUG_DIR)))

    _ensure_parent(db_path)
    _ensure_parent(auth_path)
    debug_dir.mkdir(parents=True, exist_ok=True)

    return AppConfig(db_path=db_path, auth_path=auth_path, debug_dir=debug_dir)
