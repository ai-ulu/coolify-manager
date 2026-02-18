"""
Notification System - Bildirimler
Telegram, Email, Slack, Discord entegrasyonu
"""

import logging
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Bildirim kanalları"""
    TELEGRAM = "telegram"
    EMAIL = "email"
    SLACK = "slack"
    DISCORD = "discord"
    WEBHOOK = "webhook"


@dataclass
class Notification:
    """Bildirim"""
    channel: NotificationChannel
    title: str
    message: str
    level: str = "info"  # info, warning, critical
    metadata: dict = None


class NotificationManager:
    """
    Bildirim Yöneticisi.
    Birden fazla kanaldan bildirim gönderir.
    """
    
    def __init__(self):
        self.handlers = {}
        self.telegram_chat_ids: List[str] = []
        self.email_recipients: List[str] = []
        self.slack_webhook: str = ""
        self.discord_webhook: str = ""
        self.webhook_url: str = ""
        
        # Varsayılan Telegram ID
        self.telegram_chat_ids = ["5408669173"]  # Ali
    
    def add_telegram(self, chat_id: str):
        """Telegram ID ekle"""
        if chat_id not in self.telegram_chat_ids:
            self.telegram_chat_ids.append(chat_id)
    
    def set_slack(self, webhook_url: str):
        """Slack webhook ayarla"""
        self.slack_webhook = webhook_url
    
    def set_discord(self, webhook_url: str):
        """Discord webhook ayarla"""
        self.discord_webhook = webhook_url
    
    def set_email(self, smtp_host: str, smtp_port: int, username: str, password: str, recipients: List[str]):
        """Email ayarlarını yap"""
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.email_username = username
        self.email_password = password
        self.email_recipients = recipients
    
    async def send(self, notification: Notification):
        """Bildirim gönder"""
        if notification.channel == NotificationChannel.TELEGRAM:
            await self._send_telegram(notification)
        elif notification.channel == NotificationChannel.EMAIL:
            await self._send_email(notification)
        elif notification.channel == NotificationChannel.SLACK:
            await self._send_slack(notification)
        elif notification.channel == NotificationChannel.DISCORD:
            await self._send_discord(notification)
        elif notification.channel == NotificationChannel.WEBHOOK:
            await self._send_webhook(notification)
    
    async def _send_telegram(self, notification: Notification):
        """Telegram ile gönder"""
        try:
            from telegram import Bot
            
            bot = Bot(token="7983514177:AAEk5pO0q1w209q5-Im1iRkxV6v3FS0UIP8")
            
            emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🔴"}.get(notification.level, "📢")
            
            text = f"{emoji} *{notification.title}*\n\n{notification.message}"
            
            for chat_id in self.telegram_chat_ids:
                try:
                    await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Telegram gönderim hatası ({chat_id}): {e}")
                    
        except Exception as e:
            logger.error(f"Telegram hatası: {e}")
    
    async def _send_email(self, notification: Notification):
        """Email ile gönder"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            
            if not self.smtp_host or not self.email_recipients:
                return
            
            msg = MIMEText(notification.message, 'plain', 'utf-8')
            msg['Subject'] = f"[{notification.level.upper()}] {notification.title}"
            msg['From'] = self.email_username
            msg['To'] = ", ".join(self.email_recipients)
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_username, self.email_password)
                server.send_message(msg)
                
        except Exception as e:
            logger.error(f"Email hatası: {e}")
    
    async def _send_slack(self, notification: Notification):
        """Slack ile gönder"""
        try:
            import requests
            
            if not self.slack_webhook:
                return
            
            color = {"info": "#36a64f", "warning": "#ff9800", "critical": "#f44336"}.get(notification.level, "#2196f3")
            
            payload = {
                "attachments": [{
                    "color": color,
                    "title": notification.title,
                    "text": notification.message,
                }]
            }
            
            requests.post(self.slack_webhook, json=payload, timeout=10)
            
        except Exception as e:
            logger.error(f"Slack hatası: {e}")
    
    async def _send_discord(self, notification: Notification):
        """Discord ile gönder"""
        try:
            import requests
            
            if not self.discord_webhook:
                return
            
            color = {"info": 3066993, "warning": 15105570, "critical": 15158332}.get(notification.level, 3447003)
            
            payload = {
                "embeds": [{
                    "title": notification.title,
                    "description": notification.message,
                    "color": color,
                }]
            }
            
            requests.post(self.discord_webhook, json=payload, timeout=10)
            
        except Exception as e:
            logger.error(f"Discord hatası: {e}")
    
    async def _send_webhook(self, notification: Notification):
        """Generic webhook ile gönder"""
        try:
            import requests
            
            if not self.webhook_url:
                return
            
            payload = {
                "title": notification.title,
                "message": notification.message,
                "level": notification.level,
                "metadata": notification.metadata,
                "timestamp": notification.metadata.get("timestamp") if notification.metadata else None,
            }
            
            requests.post(self.webhook_url, json=payload, timeout=10)
            
        except Exception as e:
            logger.error(f"Webhook hatası: {e}")
    
    # ==================== KOLAY METODLAR ====================
    
    async def alert(self, title: str, message: str, level: str = "info", channels: List[NotificationChannel] = None):
        """Hızlı bildirim"""
        if channels is None:
            channels = [NotificationChannel.TELEGRAM]
        
        for channel in channels:
            await self.send(Notification(
                channel=channel,
                title=title,
                message=message,
                level=level,
            ))
    
    async def system_alert(self, metric: str, value: float, threshold: float):
        """Sistem uyarısı"""
        level = "critical" if value >= threshold * 1.1 else "warning"
        
        await self.alert(
            title=f"Yüksek {metric.upper()}",
            message=f"{metric.upper()}: {value:.1f}% (Eşik: {threshold}%)",
            level=level,
        )
    
    async def deploy_notification(self, app_name: str, status: str):
        """Deploy bildirimi"""
        emoji = "✅" if status == "success" else "❌"
        
        await self.alert(
            title=f"Deploy {status.capitalize()}",
            message=f"{emoji} {app_name}: {status}",
            level="info" if status == "success" else "critical",
        )
    
    async def backup_notification(self, app_name: str, status: str, size_mb: float = 0):
        """Backup bildirimi"""
        await self.alert(
            title="Yedekleme",
            message=f"💾 {app_name}: {status}" + (f" ({size_mb:.1f}MB)" if size_mb else ""),
            level="info",
        )


# Global instance
notification_manager = NotificationManager()


def get_notification_manager() -> NotificationManager:
    return notification_manager
