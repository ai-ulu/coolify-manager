"""
Notification System.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    TELEGRAM = "telegram"
    EMAIL = "email"
    SLACK = "slack"
    DISCORD = "discord"
    WEBHOOK = "webhook"


@dataclass
class Notification:
    channel: NotificationChannel
    title: str
    message: str
    level: str = "info"
    metadata: dict = None


class NotificationManager:
    def __init__(self):
        self.handlers = {}
        default_chat_ids = os.getenv("NOTIFY_TELEGRAM_CHAT_IDS", "")
        self.telegram_chat_ids: List[str] = [c.strip() for c in default_chat_ids.split(",") if c.strip()]
        self.email_recipients: List[str] = []
        self.slack_webhook: str = ""
        self.discord_webhook: str = ""
        self.webhook_url: str = ""
        self.smtp_host: str = ""
        self.smtp_port: int = 587
        self.email_username: str = ""
        self.email_password: str = ""

    def add_telegram(self, chat_id: str):
        if chat_id not in self.telegram_chat_ids:
            self.telegram_chat_ids.append(chat_id)

    def set_slack(self, webhook_url: str):
        self.slack_webhook = webhook_url

    def set_discord(self, webhook_url: str):
        self.discord_webhook = webhook_url

    def set_email(self, smtp_host: str, smtp_port: int, username: str, password: str, recipients: List[str]):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.email_username = username
        self.email_password = password
        self.email_recipients = recipients

    async def send(self, notification: Notification):
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
        try:
            from telegram import Bot

            bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            if not bot_token or not self.telegram_chat_ids:
                return

            bot = Bot(token=bot_token)
            emoji = {"info": "i", "warning": "!", "critical": "x"}.get(notification.level, "-")
            text = f"{emoji} {notification.title}\n\n{notification.message}"
            for chat_id in self.telegram_chat_ids:
                try:
                    await bot.send_message(chat_id=chat_id, text=text)
                except Exception as exc:
                    logger.error("Telegram send error (%s): %s", chat_id, exc)
        except Exception as exc:
            logger.error("Telegram handler error: %s", exc)

    async def _send_email(self, notification: Notification):
        try:
            import smtplib
            from email.mime.text import MIMEText

            if not self.smtp_host or not self.email_recipients:
                return

            msg = MIMEText(notification.message, "plain", "utf-8")
            msg["Subject"] = f"[{notification.level.upper()}] {notification.title}"
            msg["From"] = self.email_username
            msg["To"] = ", ".join(self.email_recipients)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_username, self.email_password)
                server.send_message(msg)
        except Exception as exc:
            logger.error("Email error: %s", exc)

    async def _send_slack(self, notification: Notification):
        try:
            import requests

            if not self.slack_webhook:
                return

            color = {"info": "#36a64f", "warning": "#ff9800", "critical": "#f44336"}.get(notification.level, "#2196f3")
            payload = {"attachments": [{"color": color, "title": notification.title, "text": notification.message}]}
            requests.post(self.slack_webhook, json=payload, timeout=10)
        except Exception as exc:
            logger.error("Slack error: %s", exc)

    async def _send_discord(self, notification: Notification):
        try:
            import requests

            if not self.discord_webhook:
                return

            color = {"info": 3066993, "warning": 15105570, "critical": 15158332}.get(notification.level, 3447003)
            payload = {"embeds": [{"title": notification.title, "description": notification.message, "color": color}]}
            requests.post(self.discord_webhook, json=payload, timeout=10)
        except Exception as exc:
            logger.error("Discord error: %s", exc)

    async def _send_webhook(self, notification: Notification):
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
        except Exception as exc:
            logger.error("Webhook error: %s", exc)

    async def alert(self, title: str, message: str, level: str = "info", channels: List[NotificationChannel] = None):
        if channels is None:
            channels = [NotificationChannel.TELEGRAM]

        for channel in channels:
            await self.send(Notification(channel=channel, title=title, message=message, level=level))

    async def system_alert(self, metric: str, value: float, threshold: float):
        level = "critical" if value >= threshold * 1.1 else "warning"
        await self.alert(
            title=f"High {metric.upper()}",
            message=f"{metric.upper()}: {value:.1f}% (threshold={threshold}%)",
            level=level,
        )

    async def deploy_notification(self, app_name: str, status: str):
        await self.alert(
            title=f"Deploy {status.capitalize()}",
            message=f"{app_name}: {status}",
            level="info" if status == "success" else "critical",
        )

    async def backup_notification(self, app_name: str, status: str, size_mb: float = 0):
        msg = f"{app_name}: {status}"
        if size_mb:
            msg += f" ({size_mb:.1f}MB)"
        await self.alert(title="Backup", message=msg, level="info")


notification_manager = NotificationManager()
