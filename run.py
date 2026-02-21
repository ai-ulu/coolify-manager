#!/usr/bin/env python3
"""
Coolify Multi-Agent Autonomous Management System
Ana Çalıştırma Dosyası
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Proje dizinini ekle
sys.path.insert(0, str(Path(__file__).parent))
Path("logs").mkdir(parents=True, exist_ok=True)

from config import TELEGRAM_CONFIG
from coolify_api import get_api
from agents.monitoring_agent import get_monitoring_agent
from agents.scheduler_agent import get_scheduler_agent
from agents.coordinator_agent import get_coordinator
from telegram_bot import create_bot

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/coolify_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CoolifyManager:
    """
    Ana yönetim sınıfı.
    Tüm agent'ları koordine eder.
    """
    
    def __init__(self):
        self.monitoring = get_monitoring_agent()
        self.scheduler = get_scheduler_agent()
        self.coordinator = get_coordinator()
        self.bot = None
        self.running = False
    
    async def start(self):
        """Sistemi başlatır"""
        self.running = True
        logger.info("=" * 50)
        logger.info("🐫 Coolify Multi-Agent Sistem Başlatılıyor...")
        logger.info("=" * 50)
        
        # API bağlantısını test et
        api = get_api()
        logger.info("🔗 Coolify API test ediliyor...")
        
        if api.test_connection():
            logger.info("✅ Coolify bağlantısı başarılı!")
        else:
            logger.warning("⚠️ Coolify bağlantısı başarısız - ayarları kontrol edin")
        
        # Telegram bot kontrolü
        bot_token = TELEGRAM_CONFIG.get("bot_token")
        if bot_token:
            logger.info("🤖 Telegram Bot başlatılıyor...")
            self.bot = create_bot(bot_token)
        else:
            logger.info("⚠️ Telegram bot token ayarlanmamış - bot başlatılmadı")
        
        # Agent'ları başlat
        logger.info("📡 Agent'lar başlatılıyor...")
        
        # Monitoring başlat (arka planda)
        asyncio.create_task(self.monitoring.start_monitoring())
        logger.info("✅ Monitoring Agent aktif")
        
        # Scheduler başlat (arka planda)
        asyncio.create_task(self.scheduler.start_scheduler())
        logger.info("✅ Scheduler Agent aktif")
        
        # Sunucuları kontrol et
        await self.coordinator.check_all_servers()
        logger.info(f"✅ {len(self.coordinator.servers)} sunucu kayıtlı")
        
        logger.info("=" * 50)
        logger.info("🎉 Sistem tamamen aktif!")
        logger.info("=" * 50)
        
        # Bot varsa çalıştır
        if self.bot:
            self.bot.run()
    
    async def stop(self):
        """Sistemi durdurur"""
        self.running = False
        logger.info("🐫 Sistem kapatılıyor...")
        
        self.monitoring.stop_monitoring()
        self.scheduler.stop_scheduler()
        
        logger.info("✅ Tüm agent'lar durduruldu")


async def main():
    """Ana fonksiyon"""
    manager = CoolifyManager()
    
    # Signal handler'ları
    def signal_handler(sig, frame):
        logger.info("Signal alındı, kapatılıyor...")
        asyncio.create_task(manager.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Sistemi başlat
    await manager.start()


if __name__ == "__main__":
    asyncio.run(main())
