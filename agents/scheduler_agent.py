"""
Backup & Scheduler Agent
Yedekleme, zamanlı görevler ve bakım işlemleri
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
import uuid

from ..config import BACKUP_CONFIG
from ..coolify_api import CoolifyAPI

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Görev durumu"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(Enum):
    """Görev türü"""
    BACKUP = "backup"
    RESTORE = "restore"
    DEPLOY = "deploy"
    HEALTH_CHECK = "health_check"
    MAINTENANCE = "maintenance"
    CLEANUP = "cleanup"
    CUSTOM = "custom"


@dataclass
class ScheduledTask:
    """Zamanlı görev"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    task_type: TaskType = TaskType.CUSTOM
    cron_expression: str = ""
    command: str = ""
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    last_status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Backup:
    """Yedek bilgisi"""
    id: str
    application_id: str
    application_name: str
    status: str  # pending, running, completed, failed
    size_bytes: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = None
    error: Optional[str] = None


class SchedulerAgent:
    """
    Zamanlı görev ve yedekleme ajanı.
    Cron tabanlı görevleri çalıştırır, yedekleme işlemlerini yönetir.
    """
    
    def __init__(self, coolify_api: CoolifyAPI = None):
        self.api = coolify_api or CoolifyAPI()
        self.scheduled_tasks: List[ScheduledTask] = []
        self.backups: List[Backup] = []
        self.running = False
        self.task_history: List[Dict] = []
        self.callbacks: List[Callable] = []
        self.backup_config = BACKUP_CONFIG
    
    # ==================== SCHEDULER ====================
    
    def add_task(self, name: str, cron: str, command: str, 
                 task_type: TaskType = TaskType.CUSTOM) -> ScheduledTask:
        """Yeni scheduled görev ekler"""
        task = ScheduledTask(
            name=name,
            cron_expression=cron,
            command=command,
            task_type=task_type,
        )
        self.scheduled_tasks.append(task)
        logger.info(f"Scheduled görev eklendi: {name} ({cron})")
        return task
    
    def remove_task(self, task_id: str) -> bool:
        """Görevi siler"""
        for i, task in enumerate(self.scheduled_tasks):
            if task.id == task_id:
                self.scheduled_tasks.pop(i)
                logger.info(f"Görev silindi: {task.name}")
                return True
        return False
    
    def list_tasks(self) -> str:
        """Tüm görevleri listeler"""
        if not self.scheduled_tasks:
            return "📅 Aktif scheduled görev yok"
        
        msg = "📅 **Scheduled Görevler:**\n\n"
        for task in self.scheduled_tasks:
            status = "✅" if task.enabled else "⏸️"
            last = task.last_run.strftime("%H:%M") if task.last_run else "Henüz çalışmadı"
            next_run = task.next_run.strftime("%H:%M") if task.next_run else "-"
            
            msg += f"{status} **{task.name}**\n"
            msg += f"   Tür: {task.task_type.value}\n"
            msg += f"   Cron: `{task.cron_expression}`\n"
            msg += f"   Son: {last} | Sonraki: {next_run}\n"
            msg += f"   Durum: {task.last_status.value}\n\n"
        
        return msg
    
    def get_task_by_name(self, name: str) -> Optional[ScheduledTask]:
        """İsme göre görev bulur"""
        for task in self.scheduled_tasks:
            if task.name.lower() == name.lower():
                return task
        return None
    
    # ==================== BACKUP ====================
    
    async def create_backup(self, application_id: str, 
                          application_name: str = "") -> Backup:
        """Yedek oluşturur"""
        backup = Backup(
            id=str(uuid.uuid4())[:8],
            application_id=application_id,
            application_name=application_name or application_id,
            status="running",
        )
        self.backups.append(backup)
        
        try:
            # Coolify API çağrısı
            result = self.api.create_backup(application_id)
            
            if "error" in result:
                backup.status = "failed"
                backup.error = result.get("error")
            else:
                backup.status = "completed"
                backup.completed_at = datetime.now()
            
        except Exception as e:
            backup.status = "failed"
            backup.error = str(e)
            logger.error(f"Backup hatası: {e}")
        
        self.task_history.append({
            "type": "backup",
            "backup_id": backup.id,
            "application": backup.application_name,
            "status": backup.status,
            "timestamp": datetime.now().isoformat(),
        })
        
        return backup
    
    async def restore_backup(self, backup_id: str, application_id: str) -> bool:
        """Yedekten geri yükler"""
        try:
            result = self.api.restore_backup(application_id, backup_id)
            
            self.task_history.append({
                "type": "restore",
                "backup_id": backup_id,
                "application_id": application_id,
                "status": "completed" if "error" not in result else "failed",
                "timestamp": datetime.now().isoformat(),
            })
            
            return "error" not in result
            
        except Exception as e:
            logger.error(f"Restore hatası: {e}")
            return False
    
    def list_backups(self, application_id: str = None) -> str:
        """Yedekleri listeler"""
        if not self.backups:
            return "💾 Henüz yedek yok"
        
        filtered = self.backups
        if application_id:
            filtered = [b for b in self.backups if b.application_id == application_id]
        
        if not filtered:
            return "💾 Bu uygulama için yedek yok"
        
        msg = "💾 **Yedekler:**\n\n"
        for b in filtered:
            emoji = "✅" if b.status == "completed" else "🔄" if b.status == "running" else "❌"
            size_mb = b.size_bytes / (1024 * 1024) if b.size_bytes else 0
            
            msg += f"{emoji} **{b.application_name}**\n"
            msg += f"   ID: `{b.id}`\n"
            msg += f"   Tarih: {b.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            msg += f"   Boyut: {size_mb:.2f}MB\n"
            if b.error:
                msg += f"   Hata: {b.error}\n"
            msg += "\n"
        
        return msg
    
    def get_backup_schedule(self) -> str:
        """Yedekleme takvimini gösterir"""
        msg = "💾 **Otomatik Yedekleme Ayarları:**\n\n"
        msg += f"Aktif: {'✅ Evet' if self.backup_config['auto_backup_enabled'] else '❌ Hayır'}\n"
        msg += f"Zamanlama: `{self.backup_config['backup_schedule']}`\n"
        msg += "Her gün 02:00'de otomatik yedekleme yapılır\n\n"
        
        # Varsayılan görevleri göster
        default_tasks = [t for t in self.scheduled_tasks if t.task_type == TaskType.BACKUP]
        if default_tasks:
            msg += "**Aktif Yedekleme Görevleri:**\n"
            for t in default_tasks:
                msg += f"• {t.name} ({t.cron_expression})\n"
        
        return msg
    
    # ==================== GÖREV ÇALIŞTIRMA ====================
    
    async def execute_task(self, task: ScheduledTask) -> bool:
        """Görevi çalıştırır"""
        task.last_run = datetime.now()
        task.last_status = TaskStatus.RUNNING
        logger.info(f"Görev çalıştırılıyor: {task.name}")
        
        try:
            if task.task_type == TaskType.BACKUP:
                # Tüm uygulamaları yedekle
                apps = self.api.get_applications()
                for app in apps:
                    await self.create_backup(app.get("id", ""), app.get("name", ""))
            
            elif task.task_type == TaskType.HEALTH_CHECK:
                # Health check yap
                apps = self.api.get_applications()
                for app in apps:
                    status = self.api.get_application_status(app.get("id", ""))
            
            elif task.task_type == TaskType.CLEANUP:
                # Eski yedekleri temizle
                await self.cleanup_old_backups()
            
            else:
                # Özel komut
                logger.info(f"Özel komut çalıştırılıyor: {task.command}")
            
            task.last_status = TaskStatus.COMPLETED
            return True
            
        except Exception as e:
            task.last_status = TaskStatus.FAILED
            logger.error(f"Görev hatası: {e}")
            return False
    
    async def cleanup_old_backups(self):
        """Eski yedekleri temizler"""
        retention_days = self.backup_config["retention_days"]
        cutoff = datetime.now() - timedelta(days=retention_days)
        
        old_backups = [b for b in self.backups 
                      if b.created_at < cutoff]
        
        for backup in old_backups:
            try:
                self.api.delete_backup(backup.application_id, backup.id)
                logger.info(f"Eski yedek silindi: {backup.id}")
            except Exception as e:
                logger.error(f"Yedek silme hatası: {e}")
        
        return len(old_backups)
    
    # ==================== SCHEDULER LOOP ====================
    
    async def start_scheduler(self):
        """Scheduler döngüsünü başlatır"""
        self.running = True
        logger.info("Scheduler Agent başladı")
        
        # Varsayılan görevleri ekle
        self._setup_default_tasks()
        
        while self.running:
            try:
                now = datetime.now()
                
                # Her görevi kontrol et
                for task in self.scheduled_tasks:
                    if not task.enabled:
                        continue
                    
                    # Basit cron kontrolü (dakika bazlı)
                    # Gerçek cron için python-croniter kullanılabilir
                    if self._should_run_task(task, now):
                        await self.execute_task(task)
                        
                        # Callback'leri çağır
                        for callback in self.callbacks:
                            try:
                                callback(task)
                            except Exception as e:
                                logger.error(f"Callback hatası: {e}")
                
                await asyncio.sleep(60)  # Her dakika kontrol et
                
            except Exception as e:
                logger.error(f"Scheduler hatası: {e}")
                await asyncio.sleep(5)
    
    def _setup_default_tasks(self):
        """Varsayılan görevleri oluşturur"""
        # Otomatik yedekleme
        if self.backup_config["auto_backup_enabled"]:
            self.add_task(
                name="Otomatik Yedekleme",
                cron=self.backup_config["backup_schedule"],
                command="backup_all",
                task_type=TaskType.BACKUP,
            )
        
        # Günlük health check
        self.add_task(
            name="Günlük Health Check",
            cron="0 6 * * *",  # Her gün 06:00
            command="health_check",
            task_type=TaskType.HEALTH_CHECK,
        )
        
        # Haftalık temizlik
        self.add_task(
            name="Haftalık Temizlik",
            cron="0 3 * * 0",  # Her pazar 03:00
            command="cleanup",
            task_type=TaskType.CLEANUP,
        )
    
    def _should_run_task(self, task: ScheduledTask, now: datetime) -> bool:
        """Görevin çalışıp çalışmayacağını kontrol eder"""
        if not task.last_run:
            return True
        
        # Basit kontrol: son çalışmadan sonra 24 saat geçti mi?
        # Gerçek cron ifadesi için croniter kullanılmalı
        hours_since_last = (now - task.last_run).total_seconds() / 3600
        
        # Basit cron kontrolü
        if task.cron_expression == "0 2 * * *":  # Günlük 02:00
            return now.hour == 2 and now.minute < 1
        elif task.cron_expression == "0 6 * * *":  # Günlük 06:00
            return now.hour == 6 and now.minute < 1
        elif task.cron_expression == "0 3 * * 0":  # Haftalık pazar 03:00
            return now.hour == 3 and now.minute < 1 and now.weekday() == 6
        
        return False
    
    def stop_scheduler(self):
        """Scheduler'ı durdurur"""
        self.running = False
        logger.info("Scheduler Agent durduruldu")
    
    def register_callback(self, callback: Callable):
        """Görev tamamlandığında çağırılacak callback ekler"""
        self.callbacks.append(callback)


# Global scheduler instance
scheduler_agent = SchedulerAgent()


def get_scheduler_agent() -> SchedulerAgent:
    """Scheduler agent instance'ını döndürür"""
    return scheduler_agent
