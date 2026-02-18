"""
Coolify Multi-Agent Autonomous Management System
Konfigürasyon Dosyası
"""

import os
from pathlib import Path

# Proje dizini
BASE_DIR = Path(__file__).parent

# ==================== COOLIFY AYARLARI ====================
COOLIFY_CONFIG = {
    "url": "https://coolify.ai-ulu.com",
    "api_key": os.getenv("COOLIFY_API_KEY", "gJQaCiXa3o6Kw4e4WBT3RgmIon7ltUiEAioLLMTLb2d454bb"),
    "timeout": 30,
}

# ==================== OLLAMA AYARLARI ====================
OLLAMA_CONFIG = {
    "base_url": "http://ollama:11434",  # Docker container içinde
    "model": "llama3.2",  # Varsayılan model
    # Alternatif: "mistral", "codellama", "phi3"
}

# ==================== TELEGRAM AYARLARI ====================
TELEGRAM_CONFIG = {
    "bot_token": "7983514177:AAEk5pO0q1w209q5-Im1iRkxV6v3FS0UIP8",  # @BotFather'dan al
    "allowed_users": [],  # İzin verilen kullanıcı ID'leri (boş = herkes)
    "admin_users": [],  # Admin kullanıcı ID'leri
}

# ==================== OPENAI YEDEKLİ LLM ====================
OPENAI_CONFIG = {
    "api_key": os.getenv("OPENAI_API_KEY", ""),
    "model": "gpt-4o-mini",
    "fallback_model": "gpt-4o",
}

# ==================== ALERT EŞİK DEĞERLERİ ====================
THRESHOLDS = {
    "cpu": {
        "warning": 80,
        "critical": 90,
    },
    "ram": {
        "warning": 75,
        "critical": 90,
    },
    "disk": {
        "warning": 80,
        "critical": 90,
    },
    "response_time": {
        "warning": 2000,  # ms
        "critical": 5000,  # ms
    },
}

# ==================== BACKUP AYARLARI ====================
BACKUP_CONFIG = {
    "retention_days": 7,
    "max_backups": 10,
    "auto_backup_enabled": True,
    "backup_schedule": "0 2 * * *",  # Her gün 02:00
}

# ==================== MONITORING AYARLARI ====================
MONITORING_CONFIG = {
    "interval_seconds": 60,
    "history_hours": 24,
    "alert_cooldown_minutes": 15,
}

# ==================== LOGLAMA ====================
LOG_CONFIG = {
    "level": "INFO",
    "file": BASE_DIR / "logs" / "coolify_manager.log",
    "max_bytes": 10 * 1024 * 1024,  # 10MB
    "backup_count": 5,
}

# ==================== VERİTABANI ====================
DATABASE_CONFIG = {
    "type": "sqlite",  # sqlite veya postgresql
    "path": BASE_DIR / "data" / "coolify_manager.db",
    # PostgreSQL için:
    # "type": "postgresql",
    # "host": "localhost",
    # "port": 5432,
    # "database": "coolify_manager",
    # "user": "postgres",
    # "password": os.getenv("POSTGRES_PASSWORD", ""),
}

# ==================== SUNUCU LİSTESİ ====================
# Birden fazla Coolify sunucusu eklemek için
SERVERS = {
    "main": {
        "name": "Ana Sunucu",
        "url": "https://coolify.ai-ulu.com",
        "api_key": os.getenv("COOLIFY_API_KEY", "gJQaCiXa3o6Kw4e4WBT3RgmIon7ltUiEAioLLMTLb2d454bb"),
        "enabled": True,
    },
}

# ==================== FONKSİYONLAR ====================

def get_coolify_headers():
    """Coolify API için header döndürür"""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {COOLIFY_CONFIG['api_key']}",
    }

def get_server_config(server_name: str = "main") -> dict:
    """Belirli bir sunucu yapılandırmasını döndürür"""
    return SERVERS.get(server_name, SERVERS["main"])
