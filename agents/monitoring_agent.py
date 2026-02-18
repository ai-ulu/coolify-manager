"""
Monitoring Agent - Sistem izleme ve metrik toplama
CPU, RAM, Disk, Network, Container durumlarını takip eder
"""

import asyncio
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import deque
import logging
import json

from ..config import MONITORING_CONFIG, THRESHOLDS
from ..coolify_api import CoolifyAPI

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Tek bir metrik noktası"""
    timestamp: datetime
    value: float
    unit: str


@dataclass
class SystemMetrics:
    """Sistem metrikleri"""
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    disk_percent: float = 0.0
    disk_used_gb: float = 0.0
    disk_total_gb: float = 0.0
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0
    load_average: tuple = (0.0, 0.0, 0.0)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Alert:
    """Alarm bilgisi"""
    level: str  # info, warning, critical
    metric: str
    value: float
    threshold: float
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False


class MonitoringAgent:
    """
    Sistem izleme ajanı.
    Sürekli metrik toplar, eşik değerlerini kontrol eder ve alarm üretir.
    """
    
    def __init__(self, coolify_api: CoolifyAPI = None):
        self.api = coolify_api or CoolifyAPI()
        self.interval = MONITORING_CONFIG["interval_seconds"]
        self.history: deque = deque(maxlen=1440)  # 24 saat (dakikada bir)
        self.alerts: List[Alert] = []
        self.last_alert_time: Dict[str, datetime] = {}
        self.cooldown = timedelta(minutes=MONITORING_CONFIG["alert_cooldown_minutes"])
        self.running = False
        self.thresholds = THRESHOLDS
    
    # ==================== SİSTEM METRİKLERİ ====================
    
    async def get_system_metrics(self) -> SystemMetrics:
        """Sistem metriklerini çeker (psutil)"""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        load_avg = psutil.getloadavg()
        
        # RAM
        ram = psutil.virtual_memory()
        
        # Disk
        disk = psutil.disk_usage('/')
        
        # Network
        net = psutil.net_io_counters()
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            ram_percent=ram.percent,
            ram_used_gb=ram.used / (1024**3),
            ram_total_gb=ram.total / (1024**3),
            disk_percent=disk.percent,
            disk_used_gb=disk.used / (1024**3),
            disk_total_gb=disk.total / (1024**3),
            network_sent_mb=net.bytes_sent / (1024**2),
            network_recv_mb=net.bytes_recv / (1024**2),
            load_average=load_avg,
        )
    
    async def get_coolify_status(self) -> Dict:
        """Coolify uygulama durumlarını çeker"""
        try:
            apps = self.api.get_applications()
            resources = self.api.get_resources()
            stats = self.api.get_server_stats()
            
            return {
                "applications": apps,
                "resources": resources,
                "server_stats": stats,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Coolify status hatası: {e}")
            return {"error": str(e)}
    
    # ==================== ALARM KONTROLÜ ====================
    
    def check_thresholds(self, metrics: SystemMetrics) -> List[Alert]:
        """Eşik değerlerini kontrol eder ve alarm üretir"""
        alerts = []
        now = datetime.now()
        
        # CPU kontrolü
        alert = None
        if metrics.cpu_percent >= self.thresholds["cpu"]["critical"]:
            alert = self._create_alert(
                "critical", "cpu", metrics.cpu_percent,
                self.thresholds["cpu"]["critical"],
                f"CPU kullanımı kritik seviyede: {metrics.cpu_percent:.1f}%"
            )
        elif metrics.cpu_percent >= self.thresholds["cpu"]["warning"]:
            alert = self._create_alert(
                "warning", "cpu", metrics.cpu_percent,
                self.thresholds["cpu"]["warning"],
                f"Yüksek CPU kullanımı: {metrics.cpu_percent:.1f}%"
            )
        
        if alert and self._should_send_alert("cpu", now):
            alerts.append(alert)
        
        # RAM kontrolü
        alert = None
        if metrics.ram_percent >= self.thresholds["ram"]["critical"]:
            alert = self._create_alert(
                "critical", "ram", metrics.ram_percent,
                self.thresholds["ram"]["critical"],
                f"RAM kritik: {metrics.ram_percent:.1f}% ({metrics.ram_used_gb:.1f}GB / {metrics.ram_total_gb:.1f}GB)"
            )
        elif metrics.ram_percent >= self.thresholds["ram"]["warning"]:
            alert = self._create_alert(
                "warning", "ram", metrics.ram_percent,
                self.thresholds["ram"]["warning"],
                f"Yüksek RAM kullanımı: {metrics.ram_percent:.1f}%"
            )
        
        if alert and self._should_send_alert("ram", now):
            alerts.append(alert)
        
        # Disk kontrolü
        alert = None
        if metrics.disk_percent >= self.thresholds["disk"]["critical"]:
            alert = self._create_alert(
                "critical", "disk", metrics.disk_percent,
                self.thresholds["disk"]["critical"],
                f"Disk doluluk kritik: {metrics.disk_percent:.1f}%"
            )
        elif metrics.disk_percent >= self.thresholds["disk"]["warning"]:
            alert = self._create_alert(
                "warning", "disk", metrics.disk_percent,
                self.thresholds["disk"]["warning"],
                f"Yüksek disk kullanımı: {metrics.disk_percent:.1f}%"
            )
        
        if alert and self._should_send_alert("disk", now):
            alerts.append(alert)
        
        return alerts
    
    def _create_alert(self, level: str, metric: str, value: float, 
                     threshold: float, message: str) -> Alert:
        """Alarm oluşturur"""
        return Alert(
            level=level,
            metric=metric,
            value=value,
            threshold=threshold,
            message=message,
        )
    
    def _should_send_alert(self, metric: str, now: datetime) -> bool:
        """Alarm gönderip göndermeme kontrolü (cooldown)"""
        last_time = self.last_alert_time.get(metric)
        if last_time and (now - last_time) < self.cooldown:
            return False
        self.last_alert_time[metric] = now
        return True
    
    # ==================== TAKİP DÖNGÜSÜ ====================
    
    async def start_monitoring(self):
        """Sürekli izlemeyi başlatır"""
        self.running = True
        logger.info("Monitoring Agent başladı")
        
        while self.running:
            try:
                # Sistem metriklerini al
                metrics = await self.get_system_metrics()
                self.history.append(metrics)
                
                # Eşik kontrolü yap
                alerts = self.check_thresholds(metrics)
                self.alerts.extend(alerts)
                
                # Alarm varsa logla
                for alert in alerts:
                    logger.warning(f"ALERT [{alert.level.upper()}]: {alert.message}")
                
                # Coolify durumunu al
                coolify_status = await self.get_coolify_status()
                
                # Bekle
                await asyncio.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"Monitoring hatası: {e}")
                await asyncio.sleep(5)
    
    def stop_monitoring(self):
        """İzlemeyi durdurur"""
        self.running = False
        logger.info("Monitoring Agent durduruldu")
    
    # ==================== FORMATLAMA ====================
    
    def format_metrics(self, metrics: SystemMetrics = None) -> str:
        """Metrikleri formatlı string olarak döndürür"""
        if metrics is None:
            metrics = self.history[-1] if self.history else None
        
        if not metrics:
            return "📊 Metrik verisi yok"
        
        # CPU durumu
        cpu_emoji = "🟢" if metrics.cpu_percent < 50 else "🟡" if metrics.cpu_percent < 80 else "🔴"
        
        # RAM durumu
        ram_emoji = "🟢" if metrics.ram_percent < 50 else "🟡" if metrics.ram_percent < 80 else "🔴"
        
        # Disk durumu
        disk_emoji = "🟢" if metrics.disk_percent < 50 else "🟡" if metrics.disk_percent < 80 else "🔴"
        
        return f"""
📊 **Sistem Durumu**

{cpu_emoji} **CPU:** {metrics.cpu_percent:.1f}%
   Load: {metrics.load_average[0]:.2f} | {metrics.load_average[1]:.2f} | {metrics.load_average[2]:.2f}

{ram_emoji} **RAM:** {metrics.ram_percent:.1f}%
   {metrics.ram_used_gb:.1f}GB / {metrics.ram_total_gb:.1f}GB

{disk_emoji} **Disk:** {metrics.disk_percent:.1f}%
   {metrics.disk_used_gb:.1f}GB / {metrics.disk_total_gb:.1f}GB

📤 **Network:**
   Gönderilen: {metrics.network_sent_mb:.2f}MB
   Alınan: {metrics.network_recv_mb:.2f}MB

⏰ Son güncelleme: {metrics.timestamp.strftime('%H:%M:%S')}
"""
    
    def format_alerts(self) -> str:
        """Aktif alarmları formatlar"""
        active = [a for a in self.alerts if not a.acknowledged]
        
        if not active:
            return "✅ Aktif alarm yok"
        
        critical = [a for a in active if a.level == "critical"]
        warnings = [a for a in active if a.level == "warning"]
        
        msg = "⚠️ **Aktif Alarmlar**\n\n"
        
        if critical:
            msg += "🔴 **Kritik:**\n"
            for a in critical:
                msg += f"• {a.message}\n"
        
        if warnings:
            msg += "\n🟡 **Uyarılar:**\n"
            for a in warnings:
                msg += f"• {a.message}\n"
        
        return msg
    
    def get_top_processes(self, limit: int = 5) -> str:
        """En çok kaynak kullanan process'leri döndürür"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                if pinfo['cpu_percent'] or pinfo['memory_percent']:
                    processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # CPU'ya göre sırala
        processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
        
        msg = "🔝 **En Çok CPU Kullanan Processler:**\n\n"
        for i, p in enumerate(processes[:limit], 1):
            msg += f"{i}. {p['name']}\n   CPU: {p['cpu_percent']:.1f}% | RAM: {p['memory_percent']:.1f}%\n"
        
        return msg
    
    def get_history_summary(self, hours: int = 1) -> Dict:
        """Geçmiş metrik özetini döndürür"""
        if not self.history:
            return {}
        
        now = datetime.now()
        cutoff = now - timedelta(hours=hours)
        relevant = [m for m in self.history if m.timestamp >= cutoff]
        
        if not relevant:
            return {}
        
        return {
            "cpu_avg": sum(m.cpu_percent for m in relevant) / len(relevant),
            "cpu_max": max(m.cpu_percent for m in relevant),
            "ram_avg": sum(m.ram_percent for m in relevant) / len(relevant),
            "ram_max": max(m.ram_percent for m in relevant),
            "disk_avg": sum(m.disk_percent for m in relevant) / len(relevant),
            "disk_max": max(m.disk_percent for m in relevant),
            "samples": len(relevant),
        }


# Global monitoring instance
monitoring_agent = MonitoringAgent()


def get_monitoring_agent() -> MonitoringAgent:
    """Monitoring agent instance'ını döndürür"""
    return monitoring_agent
