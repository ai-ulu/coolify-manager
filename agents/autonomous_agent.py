"""
Autonomous Agent - automated remediation and housekeeping.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

from config import AUTONOMOUS_CONFIG, THRESHOLDS
from coolify_api import CoolifyAPI

logger = logging.getLogger(__name__)


class ActionType(Enum):
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
    action_type: ActionType
    target: str
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)
    executed: bool = False
    success: Optional[bool] = None


@dataclass
class AutoScaleRule:
    metric: str
    threshold: float
    action: str
    scale_by: int = 1
    cooldown_minutes: int = 15


class AutonomousAgent:
    def __init__(self, coolify_api: CoolifyAPI = None, telegram_callback: Callable = None):
        self.api = coolify_api or CoolifyAPI()
        self.telegram_callback = telegram_callback
        self.thresholds = THRESHOLDS
        self.running = False
        self.actions: List[AutonomousAction] = []
        self.cooldowns: Dict[str, datetime] = {}
        self.cooldown_minutes = 15
        self.health_check_failures: Dict[str, int] = {}
        self.max_failures = 3
        self.disk_target = "C:\\" if os.name == "nt" else "/"
        self.scale_rules = [
            AutoScaleRule(metric="cpu", threshold=85, action="up", scale_by=1),
            AutoScaleRule(metric="ram", threshold=85, action="up", scale_by=1),
            AutoScaleRule(metric="cpu", threshold=30, action="down", scale_by=-1),
            AutoScaleRule(metric="ram", threshold=30, action="down", scale_by=-1),
        ]

    async def start(self):
        self.running = True
        logger.info("Autonomous Agent started")

        while self.running:
            try:
                await self.check_system_metrics()
                await self.check_application_health()
                await self.check_disk_space()
                await asyncio.sleep(60)
            except Exception as exc:
                logger.error("Autonomous loop error: %s", exc)
                await asyncio.sleep(10)

    def stop(self):
        self.running = False
        logger.info("Autonomous Agent stopped")

    async def check_system_metrics(self):
        import psutil

        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage(self.disk_target).percent

        if cpu >= self.thresholds["cpu"]["critical"]:
            await self.execute_action(ActionType.ALERT, "system", f"Critical CPU: {cpu:.1f}%")
        elif cpu >= self.thresholds["cpu"]["warning"]:
            await self.execute_action(ActionType.ALERT, "system", f"High CPU: {cpu:.1f}%")

        if ram >= self.thresholds["ram"]["critical"]:
            await self.execute_action(ActionType.ALERT, "system", f"Critical RAM: {ram:.1f}%")

        if disk >= self.thresholds["disk"]["critical"]:
            await self.execute_action(ActionType.CLEANUP, "disk", "Disk is critical, cleanup triggered")
            await self.cleanup_old_files()
        elif disk >= self.thresholds["disk"]["warning"]:
            await self.execute_action(ActionType.ALERT, "disk", f"High disk usage: {disk:.1f}%")

    async def check_application_health(self):
        apps = self.api.get_applications()
        if not apps:
            return

        for app in apps:
            app_id = app.get("id")
            app_name = app.get("name", "unknown")
            status = str(app.get("status", "")).lower()
            if not app_id:
                continue

            if status != "running":
                self.health_check_failures[app_id] = self.health_check_failures.get(app_id, 0) + 1
                if self.health_check_failures[app_id] >= self.max_failures:
                    await self.execute_action(ActionType.HEAL, app_name, "App unhealthy for 3 checks, restarting")
                    await self.heal_application(app_id)
                    self.health_check_failures[app_id] = 0
            else:
                self.health_check_failures[app_id] = 0

    async def check_disk_space(self):
        import psutil

        disk = psutil.disk_usage(self.disk_target)
        if disk.percent >= 90:
            await self.cleanup_old_files()
            await self.execute_action(ActionType.CLEANUP, "disk", f"Emergency cleanup done at {disk.percent:.1f}%")

    async def cleanup_old_files(self) -> int:
        if not AUTONOMOUS_CONFIG["cleanup_enabled"]:
            return 0

        cleaned = 0
        cleanup_paths = AUTONOMOUS_CONFIG["cleanup_paths"]
        retention_days = AUTONOMOUS_CONFIG["cleanup_days"]

        if not cleanup_paths:
            return 0

        import glob

        for raw_dir in cleanup_paths:
            safe_dir = Path(raw_dir).expanduser().resolve()
            if not safe_dir.exists() or not safe_dir.is_dir():
                continue

            for log_file in glob.glob(str(safe_dir / "*.log")):
                try:
                    mtime = os.path.getmtime(log_file)
                    age_days = (datetime.now().timestamp() - mtime) / 86400
                    if age_days > retention_days:
                        os.remove(log_file)
                        cleaned += 1
                except OSError:
                    continue

        return cleaned

    async def heal_application(self, app_id: str):
        self.api.stop_application(app_id)
        await asyncio.sleep(2)
        self.api.start_application(app_id)

    async def execute_action(self, action_type: ActionType, target: str, reason: str):
        cooldown_key = f"{action_type.value}_{target}"
        last_time = self.cooldowns.get(cooldown_key)
        if last_time and (datetime.now() - last_time).seconds < self.cooldown_minutes * 60:
            return

        action = AutonomousAction(action_type=action_type, target=target, reason=reason, executed=True)
        self.actions.append(action)
        self.cooldowns[cooldown_key] = datetime.now()

        if self.telegram_callback:
            try:
                await self.telegram_callback(
                    f"*Autonomous Action*\nType: {action_type.value}\nTarget: {target}\nReason: {reason}"
                )
            except Exception as exc:
                logger.error("Notification error: %s", exc)

        logger.info("Autonomous action: %s %s %s", action_type.value, target, reason)

    def get_actions_log(self, limit: int = 10) -> str:
        if not self.actions:
            return "No autonomous actions yet"

        lines = ["*Autonomous Action History:*", ""]
        for action in self.actions[-limit:]:
            lines.append(f"- {action.action_type.value} {action.target}: {action.reason}")
            lines.append(f"  {action.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        return "\n".join(lines)

    async def trigger_backup(self):
        await self.execute_action(ActionType.BACKUP, "all", "Manual backup requested")


autonomous_agent = AutonomousAgent()


def get_autonomous_agent() -> AutonomousAgent:
    return autonomous_agent
