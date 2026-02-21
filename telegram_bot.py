"""
Telegram bot interface for Coolify manager.
"""

import logging
from typing import Dict, Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import TELEGRAM_CONFIG
from coolify_api import CoolifyAPI
from agents.coordinator_agent import get_coordinator
from agents.monitoring_agent import get_monitoring_agent
from agents.scheduler_agent import get_scheduler_agent

logger = logging.getLogger(__name__)


class CoolifyBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.api = CoolifyAPI()
        self.monitoring = get_monitoring_agent()
        self.scheduler = get_scheduler_agent()
        self.coordinator = get_coordinator()
        self.user_sessions: Dict[str, Dict] = {}
        self.allowed_users = set(TELEGRAM_CONFIG.get("allowed_users", []))
        self.admin_users = set(TELEGRAM_CONFIG.get("admin_users", []))
        self._register_commands()

    def _register_commands(self):
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("metrics", self.cmd_metrics))
        self.app.add_handler(CommandHandler("cpu", self.cmd_cpu))
        self.app.add_handler(CommandHandler("ram", self.cmd_ram))
        self.app.add_handler(CommandHandler("disk", self.cmd_disk))
        self.app.add_handler(CommandHandler("top", self.cmd_top))
        self.app.add_handler(CommandHandler("alerts", self.cmd_alerts))

        self.app.add_handler(CommandHandler("list", self.cmd_list))
        self.app.add_handler(CommandHandler("deploy", self.cmd_deploy))
        self.app.add_handler(CommandHandler("startapp", self.cmd_start_app))
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
        self.app.add_handler(CommandHandler("restart", self.cmd_restart))
        self.app.add_handler(CommandHandler("logs", self.cmd_logs))

        self.app.add_handler(CommandHandler("backup", self.cmd_backup))
        self.app.add_handler(CommandHandler("backups", self.cmd_backups))
        self.app.add_handler(CommandHandler("restore", self.cmd_restore))

        self.app.add_handler(CommandHandler("schedule", self.cmd_schedule))
        self.app.add_handler(CommandHandler("servers", self.cmd_servers))

        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    def _user_id(self, update: Update) -> int:
        return update.effective_user.id if update and update.effective_user else 0

    async def _check_allowed(self, update: Update) -> bool:
        user_id = self._user_id(update)
        if not self.allowed_users:
            return True
        if user_id in self.allowed_users or user_id in self.admin_users:
            return True
        if update.message:
            await update.message.reply_text("Unauthorized user")
        logger.warning("Unauthorized user blocked: %s", user_id)
        return False

    async def _check_admin(self, update: Update) -> bool:
        if not await self._check_allowed(update):
            return False
        user_id = self._user_id(update)
        if not self.admin_users or user_id in self.admin_users:
            return True
        if update.message:
            await update.message.reply_text("Admin permission required")
        logger.warning("Non-admin command blocked: %s", user_id)
        return False

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        await update.message.reply_text(
            "Coolify Manager\n\n"
            "Commands:\n"
            "/help\n/status\n/metrics\n/list\n/servers\n"
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        await update.message.reply_text(
            "Monitoring:\n"
            "/status /metrics /cpu /ram /disk /top /alerts\n\n"
            "Applications:\n"
            "/list /deploy <name> /startapp <name> /stop <name> /restart <name> /logs <name>\n\n"
            "Backup:\n"
            "/backup [name] /backups /restore <backup_id> <app_id>\n\n"
            "Scheduler:\n"
            "/schedule /servers"
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        metrics = self.monitoring.format_metrics()
        alerts = self.monitoring.format_alerts()
        server_status = self.coordinator.get_unified_status()
        await update.message.reply_text(f"{server_status}\n\n{metrics}\n\n{alerts}")

    async def cmd_metrics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        await update.message.reply_text(self.monitoring.format_metrics())

    async def cmd_cpu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        metrics = self.monitoring.history[-1] if self.monitoring.history else None
        if not metrics:
            await update.message.reply_text("No metrics")
            return
        await update.message.reply_text(f"CPU: {metrics.cpu_percent:.1f}%")

    async def cmd_ram(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        metrics = self.monitoring.history[-1] if self.monitoring.history else None
        if not metrics:
            await update.message.reply_text("No metrics")
            return
        await update.message.reply_text(
            f"RAM: {metrics.ram_percent:.1f}% ({metrics.ram_used_gb:.1f}/{metrics.ram_total_gb:.1f} GB)"
        )

    async def cmd_disk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        metrics = self.monitoring.history[-1] if self.monitoring.history else None
        if not metrics:
            await update.message.reply_text("No metrics")
            return
        await update.message.reply_text(
            f"Disk: {metrics.disk_percent:.1f}% ({metrics.disk_used_gb:.1f}/{metrics.disk_total_gb:.1f} GB)"
        )

    async def cmd_top(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        await update.message.reply_text(self.monitoring.get_top_processes())

    async def cmd_alerts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        await update.message.reply_text(self.monitoring.format_alerts())

    async def cmd_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        apps = self.api.get_applications()
        if not apps:
            await update.message.reply_text("No application found")
            return
        lines = ["Applications:"]
        for app in apps[:20]:
            lines.append(f"- {app.get('name', 'unknown')} [{app.get('status', 'unknown')}]")
        await update.message.reply_text("\n".join(lines))

    async def _find_app_by_name(self, app_name: str):
        apps = self.api.get_applications()
        return next((a for a in apps if a.get("name", "").lower() == app_name.lower()), None)

    async def cmd_deploy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_admin(update):
            return
        app_name = context.args[0] if context.args else None
        if not app_name:
            await update.message.reply_text("Usage: /deploy <app_name>")
            return
        app = await self._find_app_by_name(app_name)
        if not app:
            await update.message.reply_text("Application not found")
            return
        result = self.api.deploy_application(app.get("id"))
        await update.message.reply_text("Deploy started" if "error" not in result else f"Deploy error: {result.get('error')}")

    async def cmd_start_app(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_admin(update):
            return
        app_name = context.args[0] if context.args else None
        if not app_name:
            await update.message.reply_text("Usage: /startapp <app_name>")
            return
        app = await self._find_app_by_name(app_name)
        if not app:
            await update.message.reply_text("Application not found")
            return
        result = self.api.start_application(app.get("id"))
        await update.message.reply_text("Start requested" if "error" not in result else f"Error: {result.get('error')}")

    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_admin(update):
            return
        app_name = context.args[0] if context.args else None
        if not app_name:
            await update.message.reply_text("Usage: /stop <app_name>")
            return
        app = await self._find_app_by_name(app_name)
        if not app:
            await update.message.reply_text("Application not found")
            return
        result = self.api.stop_application(app.get("id"))
        await update.message.reply_text("Stop requested" if "error" not in result else f"Error: {result.get('error')}")

    async def cmd_restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_admin(update):
            return
        app_name = context.args[0] if context.args else None
        if not app_name:
            await update.message.reply_text("Usage: /restart <app_name>")
            return
        app = await self._find_app_by_name(app_name)
        if not app:
            await update.message.reply_text("Application not found")
            return
        result = self.api.restart_application(app.get("id"))
        await update.message.reply_text("Restart requested" if "error" not in result else f"Error: {result.get('error')}")

    async def cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        app_name = context.args[0] if context.args else None
        if not app_name:
            await update.message.reply_text("Usage: /logs <app_name>")
            return
        app = await self._find_app_by_name(app_name)
        if not app:
            await update.message.reply_text("Application not found")
            return
        logs = self.api.get_application_logs(app.get("id"), limit=20)
        logs = logs[-3500:] if len(logs) > 3500 else logs
        await update.message.reply_text(f"Logs for {app_name}:\n{logs}")

    async def cmd_backup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_admin(update):
            return
        app_name = context.args[0] if context.args else None
        if app_name:
            app = await self._find_app_by_name(app_name)
            if not app:
                await update.message.reply_text("Application not found")
                return
            backup = await self.scheduler.create_backup(app.get("id"), app.get("name"))
            await update.message.reply_text(f"Backup status={backup.status}, id={backup.id}")
            return

        apps = self.api.get_applications()
        for app in apps[:10]:
            await self.scheduler.create_backup(app.get("id"), app.get("name"))
        await update.message.reply_text(f"Backup requested for {min(len(apps), 10)} apps")

    async def cmd_backups(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        await update.message.reply_text(self.scheduler.list_backups())

    async def cmd_restore(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_admin(update):
            return
        backup_id = context.args[0] if context.args else None
        app_id = context.args[1] if len(context.args) > 1 else None
        if not backup_id or not app_id:
            await update.message.reply_text("Usage: /restore <backup_id> <app_id>")
            return
        result = await self.scheduler.restore_backup(backup_id, app_id)
        await update.message.reply_text("Restore completed" if result else "Restore failed")

    async def cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        await update.message.reply_text(self.scheduler.list_tasks())

    async def cmd_servers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        await self.coordinator.check_all_servers()
        await update.message.reply_text(self.coordinator.list_servers())

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_allowed(update):
            return
        await update.message.reply_text("Use /help for command list")

    async def send_alert(self, chat_id: str, message: str):
        try:
            await self.app.bot.send_message(chat_id=chat_id, text=message)
        except Exception as exc:
            logger.error("Alert send error: %s", exc)

    def run(self):
        logger.info("Telegram bot polling started")
        # Running in worker thread: disable signal handlers to avoid set_wakeup_fd errors.
        self.app.run_polling(drop_pending_updates=True, stop_signals=None)


bot: Optional[CoolifyBot] = None


def create_bot(token: str) -> CoolifyBot:
    global bot
    bot = CoolifyBot(token)
    return bot


def get_bot() -> Optional[CoolifyBot]:
    return bot
