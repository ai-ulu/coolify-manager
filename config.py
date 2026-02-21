"""
Runtime configuration for Coolify autonomous manager.
"""

import os
from pathlib import Path
from typing import List


BASE_DIR = Path(__file__).parent


def _getenv(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


def _getenv_int(name: str, default: int) -> int:
    try:
        return int(_getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _getenv_bool(name: str, default: bool) -> bool:
    value = _getenv(name, str(default)).lower()
    return value in {"1", "true", "yes", "on"}


def _parse_int_list(value: str) -> List[int]:
    if not value:
        return []
    result: List[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            result.append(int(item))
        except ValueError:
            continue
    return result


COOLIFY_CONFIG = {
    "url": _getenv("COOLIFY_API_URL", "http://localhost:8000"),
    "api_key": _getenv("COOLIFY_API_KEY", ""),
    "timeout": _getenv_int("COOLIFY_API_TIMEOUT", 30),
}

OLLAMA_CONFIG = {
    "base_url": _getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
    "model": _getenv("OLLAMA_MODEL", "llama3.2"),
}

TELEGRAM_CONFIG = {
    "bot_token": _getenv("TELEGRAM_BOT_TOKEN", ""),
    "allowed_users": _parse_int_list(_getenv("TELEGRAM_ALLOWED_USERS", "")),
    "admin_users": _parse_int_list(_getenv("TELEGRAM_ADMIN_USERS", "")),
}

OPENAI_CONFIG = {
    "api_key": _getenv("OPENAI_API_KEY", ""),
    "model": _getenv("OPENAI_MODEL", "gpt-4o-mini"),
    "fallback_model": _getenv("OPENAI_FALLBACK_MODEL", "gpt-4o"),
}

LLM_CONFIG = {
    "enabled": _getenv_bool("LLM_ROUTER_ENABLED", True),
    "api_base": _getenv("LITELLM_API_BASE", ""),
    "api_key": _getenv("LITELLM_API_KEY", ""),
    "model": _getenv("LITELLM_MODEL", "gpt-4o-mini"),
}

THRESHOLDS = {
    "cpu": {
        "warning": _getenv_int("THRESHOLD_CPU_WARNING", 80),
        "critical": _getenv_int("THRESHOLD_CPU_CRITICAL", 90),
    },
    "ram": {
        "warning": _getenv_int("THRESHOLD_RAM_WARNING", 75),
        "critical": _getenv_int("THRESHOLD_RAM_CRITICAL", 90),
    },
    "disk": {
        "warning": _getenv_int("THRESHOLD_DISK_WARNING", 80),
        "critical": _getenv_int("THRESHOLD_DISK_CRITICAL", 90),
    },
    "response_time": {
        "warning": _getenv_int("THRESHOLD_RESPONSE_WARNING_MS", 2000),
        "critical": _getenv_int("THRESHOLD_RESPONSE_CRITICAL_MS", 5000),
    },
}

BACKUP_CONFIG = {
    "retention_days": _getenv_int("BACKUP_RETENTION_DAYS", 7),
    "max_backups": _getenv_int("BACKUP_MAX_BACKUPS", 10),
    "auto_backup_enabled": _getenv_bool("BACKUP_AUTO_ENABLED", True),
    "backup_schedule": _getenv("BACKUP_SCHEDULE", "0 2 * * *"),
}

MONITORING_CONFIG = {
    "interval_seconds": _getenv_int("MONITOR_INTERVAL_SECONDS", 60),
    "history_hours": _getenv_int("MONITOR_HISTORY_HOURS", 24),
    "alert_cooldown_minutes": _getenv_int("MONITOR_ALERT_COOLDOWN_MINUTES", 15),
}

AUTONOMOUS_CONFIG = {
    "cleanup_enabled": _getenv_bool("AUTO_CLEANUP_ENABLED", False),
    "cleanup_paths": [p.strip() for p in _getenv("AUTO_CLEANUP_PATHS", "").split(",") if p.strip()],
    "cleanup_days": _getenv_int("AUTO_CLEANUP_DAYS", 7),
}

LOG_CONFIG = {
    "level": _getenv("LOG_LEVEL", "INFO"),
    "file": BASE_DIR / "logs" / "coolify_manager.log",
    "max_bytes": 10 * 1024 * 1024,
    "backup_count": 5,
}

DATABASE_CONFIG = {
    "type": _getenv("DATABASE_TYPE", "sqlite"),
    "path": BASE_DIR / "data" / "coolify_manager.db",
}

SERVERS = {
    "main": {
        "name": _getenv("COOLIFY_SERVER_NAME", "main"),
        "url": _getenv("COOLIFY_API_URL", COOLIFY_CONFIG["url"]),
        "api_key": _getenv("COOLIFY_API_KEY", COOLIFY_CONFIG["api_key"]),
        "enabled": _getenv_bool("COOLIFY_SERVER_ENABLED", True),
    },
}


def get_coolify_headers(api_key: str = ""):
    key = api_key or COOLIFY_CONFIG["api_key"]
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def get_server_config(server_name: str = "main") -> dict:
    return SERVERS.get(server_name, SERVERS["main"])
