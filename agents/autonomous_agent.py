"""
Autonomous Agent - Otonom Yönetim
Otomatik karar verme ve eylemler
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass, field
from enum import Enum

from ..config import THRESHOLDS, BACKUP_CONFIG
from ..coolify_api import CoolifyAPI

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Eylem türleri"""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    RESTART = "restart"
    BACKUP = "backup"
    CLEANUP = "cleanup"
    ALERT = "alert"
    SCALE_AUTO = "scale_auto"
    HEAL = "heal"


@dataclass
class AutonomousAction:
    """Otonom eylem"""
    action_type: ActionType
    target: str
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)
    executed: bool = False
    success: Optional[bool] = None


@dataclass
class AutoScaleRule:
    """Otomatik ölçekleme kuralı"""
    metric: str  # cpu, ram
    threshold: float
    action: str  # up, down
    scale_by: int = 1
    cooldown_minutes: int = 15


class AutonomousAgent:
    """
    Otonom Yönetim Ajanı.
    Sistemi sürekli izler, eşik aşılınca otomatik aksiyon alır.
    """
    
    def __init__(self, coolify_api: CoolifyAPI = None, telegram_callback: Callable = None):
        self.api = coolify_api or CoolifyAPI()
        self.telegram_callback = telegram_callback
        self.thresholds = THRESHOLDS
        self.running = False
        self.actions: List[AutonomousAction] = []
        self.cooldowns: Dict[str, datetime] = {}
        self.cooldown_minutes = 15
        
        # Otomatik ölçekleme kuralları
        self.scale_rules = [
            AutoScaleRule(metric="cpu", threshold=85, action="up", scale_by=1),
            AutoScaleRule(metric="ram", threshold=85, action="up", scale_by=1),
            AutoScaleRule(metric="cpu", threshold=30, action="down", scale_by=-1),
            AutoScaleRule(metric="ram", threshold=30, action="down", scale_by=-1),
        ]
        
        # Healt check ayarları
        self.health_check_failures: Dict[str, int] = {}
        self.max_failures = 3
    
    async def start(self):
        """Otonom izlemeyi başlatır"""
        self.running = True
        logger.info("🤖 Autonomous Agent başladı")
        
        while self.running:
            try:
                # 1. Sistem metriklerini kontrol et
                await self.check_system_metrics()
                
                # 2. Uygulama sağlığını kontrol et
                await self.check_application_health()
                
                # 3. Disk kontrolü
                await self.check_disk_space()
                
                await asyncio.sleep(60)  # Her dakika kontrol
                
            except Exception as e:
                logger.error(f"Autonomous agent hatası: {e}")
                await asyncio.sleep(10)
    
    def stop(self):
        """Durdurur"""
        self.running = False
        logger.info("Autonomous Agent durduruldu")
    
    async def check_system_metrics(self):
        """Sistem metriklerini kontrol eder"""
        try:
            import psutil
            
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            
            # CPU kontrolü
            if cpu >= self.thresholds["cpu"]["critical"]:
                await self.execute_action(ActionType.ALERT, "system", 
                    f"🔴 Kritik CPU: {cpu:.1f}%")
            elif cpu >= self.thresholds["cpu"]["warning"]:
                await self.execute_action(ActionType.ALERT, "system",
                    f"🟡 Yüksek CPU: {cpu:.1f}%")
            
            # RAM kontrolü
            if ram >= self.thresholds["ram"]["critical"]:
                await self.execute_action(ActionType.ALERT, "system",
                    f"🔴 Kritik RAM: {ram:.1f}%")
            
            # Disk kontrolü
            if disk >= self.thresholds["disk"]["critical"]:
                await self.execute_action(ActionType.CLEANUP, "disk",
                    "Disk kritik seviyede, temizlik başlatılıyor")
                await self.cleanup_old_files()
            elif disk >= self.thresholds["disk"]["warning"]:
                await self.execute_action(ActionType.ALERT, "disk",
                    f"🟡 Yüksek Disk: {disk:.1f}%")
                    
        except Exception as e:
            logger.error(f"Metrik kontrolü hatası: {e}")
    
    async def check_application_health(self):
        """Uygulama sağlığını kontrol eder"""
        try:
            apps = self.api.get_applications()
            if not apps or "error" in str(apps):
                return
            
            for app in apps:
                app_id = app.get("id")
                app_name = app.get("name", "unknown")
                status = app.get("status", "").lower()
                
                # Durumu kapalıysa
                if status != "running":
                    self.health_check_failures[app_id] = self.health_check_failures.get(app_id, 0) + 1
                    
                    if self.health_check_failures[app_id] >= self.max_failures:
                        # Auto-heal: yeniden başlat
                        await self.execute_action(ActionType.HEAL, app_name,
                            f"Uygulama {self.max_failures} kez başarısız, yeniden başlatılıyor")
                        await self.heal_application(app_id)
                        self.health_check_failures[app_id] = 0
                else:
                    self.health_check_failures[app_id] = 0
                    
        except Exception as e:
            logger.error(f"Health check hatası: {e}")
    
    async def check_disk_space(self):
        """Disk alanı kontrolü ve temizlik"""
        try:
            import psutil
            disk = psutil.disk_usage('/')
            
            if disk.percent >= 90:
                # Kritik - hemen temizle
                await self.cleanup_old_files()
                await self.execute_action(ActionType.CLEANUP, "disk",
                    f"Disk {disk.percent}%, acil temizlik yapıldı")
                    
        except Exception as e:
            logger.error(f"Disk kontrolü hatası: {e}")
    
    async def cleanup_old_files(self):
        """Eski dosyaları temizler"""
        cleaned = 0
        
        # Log dosyalarını temizle
        log_paths = [
            "/var/log",
            "/tmp",
        ]
        
        try:
            import os
            import glob
            
            for log_dir in log_paths:
                if os.path.exists(log_dir):
                    # 7 günden eski logları sil
                    for log_file in glob.glob(f"{log_dir}/*.log"):
                        try:
                            mtime = os.path.getmtime(log_file)
                            age_days = (datetime.now().timestamp() - mtime) / 86400
                            if age_days > 7:
                                os.remove(log_file)
                                cleaned += 1
                        except:
                            pass
                            
        except Exception as e:
            logger.error(f"Temizlik hatası: {e}")
        
        return cleaned
    
    async def heal_application(self, app_id: str):
        """Uygulamayı yeniden başlatır (auto-heal)"""
        try:
            # Önce durdur
            self.api.stop_application(app_id)
            await asyncio.sleep(2)
            # Sonra başlat
            self.api.start_application(app_id)
            logger.info(f"Uygulama heal edildi: {app_id}")
        except Exception as e:
            logger.error(f"Heal hatası: {e}")
    
    async def execute_action(self, action_type: ActionType, target: str, reason: str):
        """Eylemi kaydeder ve bildirim gönderir"""
        
        # Cooldown kontrolü
        cooldown_key = f"{action_type.value}_{target}"
        last_time = self.cooldowns.get(cooldown_key)
        
        if last_time and (datetime.now() - last_time).seconds < self.cooldown_minutes * 60:
            return  # Cooldown'da, aksiyon alma
        
        action = AutonomousAction(
            action_type=action_type,
            target=target,
            reason=reason,
            executed=True
        )
        self.actions.append(action)
        self.cooldowns[cooldown_key] = datetime.now()
        
        # Telegram bildirimi gönder
        if self.telegram_callback:
            try:
                await self.telegram_callback(
                    f"🤖 *Otonom Eylem*\n\n"
                    f"📌 *Tür:* {action_type.value}\n"
                    f"🎯 *Hedef:* {target}\n"
                    f"📝 *Neden:* {reason}"
                )
            except Exception as e:
                logger.error(f"Bildirim hatası: {e}")
        
        logger.info(f"Otonom eylem: {action_type.value} - {target} - {reason}")
    
    def get_actions_log(self, limit: int = 10) -> str:
        """Eylem geçmişini döndürür"""
        if not self.actions:
            return "📝 Otonom eylem yok"
        
        msg = "🤖 *Otonom Eylem Geçmişi:*\n\n"
        
        for action in self.actions[-limit:]:
            emoji = {
                ActionType.SCALE_UP: "⬆️",
                ActionType.SCALE_DOWN: "⬇️",
                ActionType.RESTART: "🔄",
                ActionType.BACKUP: "💾",
                ActionType.CLEANUP: "🧹",
                ActionType.ALERT: "⚠️",
                ActionType.HEAL: "🏥",
            }.get(action.action_type, "📌")
            
            msg += f"{emoji} *{action.action_type.value}*\n"
            msg += f"   {action.target}: {action.reason}\n"
            msg += f"   {action.timestamp.strftime('%H:%M:%S')}\n\n"
        
        return msg
    
    async def trigger_backup(self):
        """Manuel yedekleme tetikle"""
        await self.execute_action(ActionType.BACKUP, "all", "Manuel yedekleme başlatıldı")
        
        try:
            apps = self.api.get_applications()
            if apps and "error" not in str(apps):
                for app in apps[:5]:  # İlk 5 uygulama
                    await asyncio.sleep(1)
                    # Backup API çağrısı
                    logger.info(f"Yedekleme: {app.get('name')}")
        except Exception as e:
            logger.error(f"Yedekleme hatası: {e}")


# Global instance
autonomous_agent = AutonomousAgent()


def get_autonomous_agent() -> AutonomousAgent:
    return autonomous_agent
