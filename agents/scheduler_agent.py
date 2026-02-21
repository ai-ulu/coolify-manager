"""
Backup and scheduler agent.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Dict, List, Optional

from croniter import croniter

from config import BACKUP_CONFIG
from coolify_api import CoolifyAPI

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(Enum):
    BACKUP = "backup"
    RESTORE = "restore"
    DEPLOY = "deploy"
    HEALTH_CHECK = "health_check"
    MAINTENANCE = "maintenance"
    CLEANUP = "cleanup"
    CUSTOM = "custom"


@dataclass
class ScheduledTask:
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
    id: str
    application_id: str
    application_name: str
    status: str
    provider_backup_id: Optional[str] = None
    size_bytes: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = None
    error: Optional[str] = None


class SchedulerAgent:
    def __init__(self, coolify_api: CoolifyAPI = None):
        self.api = coolify_api or CoolifyAPI()
        self.scheduled_tasks: List[ScheduledTask] = []
        self.backups: List[Backup] = []
        self.running = False
        self.task_history: List[Dict] = []
        self.callbacks: List[Callable] = []
        self.backup_config = BACKUP_CONFIG

    def add_task(self, name: str, cron: str, command: str, task_type: TaskType = TaskType.CUSTOM) -> ScheduledTask:
        task = ScheduledTask(name=name, cron_expression=cron, command=command, task_type=task_type)
        task.next_run = self._calculate_next_run(task.cron_expression)
        self.scheduled_tasks.append(task)
        logger.info("Scheduled task added: %s (%s)", name, cron)
        return task

    def remove_task(self, task_id: str) -> bool:
        for i, task in enumerate(self.scheduled_tasks):
            if task.id == task_id:
                self.scheduled_tasks.pop(i)
                logger.info("Task removed: %s", task.name)
                return True
        return False

    def list_tasks(self) -> str:
        if not self.scheduled_tasks:
            return "No active scheduled task"

        lines = ["*Scheduled Tasks:*", ""]
        for task in self.scheduled_tasks:
            status = "enabled" if task.enabled else "disabled"
            last_run = task.last_run.strftime("%Y-%m-%d %H:%M") if task.last_run else "never"
            next_run = task.next_run.strftime("%Y-%m-%d %H:%M") if task.next_run else "-"
            lines.append(f"- {task.name} ({task.task_type.value}) [{status}]")
            lines.append(f"  cron={task.cron_expression} last={last_run} next={next_run} state={task.last_status.value}")

        return "\n".join(lines)

    async def create_backup(self, application_id: str, application_name: str = "") -> Backup:
        backup = Backup(
            id=str(uuid.uuid4())[:8],
            application_id=application_id,
            application_name=application_name or application_id,
            status="running",
        )
        self.backups.append(backup)

        try:
            result = self.api.create_backup(application_id)
            if "error" in result:
                backup.status = "failed"
                backup.error = result.get("error")
            else:
                backup.status = "completed"
                backup.completed_at = datetime.now()
                backup.provider_backup_id = str(result.get("id") or result.get("backup_id") or "") or None
        except Exception as exc:
            backup.status = "failed"
            backup.error = str(exc)
            logger.error("Backup error: %s", exc)

        self.task_history.append(
            {
                "type": "backup",
                "backup_id": backup.id,
                "provider_backup_id": backup.provider_backup_id,
                "application": backup.application_name,
                "status": backup.status,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return backup

    async def restore_backup(self, backup_id: str, application_id: str) -> bool:
        try:
            target_id = backup_id
            match = next((b for b in self.backups if b.id == backup_id), None)
            if match and match.provider_backup_id:
                target_id = match.provider_backup_id

            result = self.api.restore_backup(application_id, target_id)
            self.task_history.append(
                {
                    "type": "restore",
                    "backup_id": backup_id,
                    "provider_backup_id": target_id,
                    "application_id": application_id,
                    "status": "completed" if "error" not in result else "failed",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            return "error" not in result
        except Exception as exc:
            logger.error("Restore error: %s", exc)
            return False

    def list_backups(self, application_id: str = None) -> str:
        if not self.backups:
            return "No backup yet"

        filtered = self.backups if not application_id else [b for b in self.backups if b.application_id == application_id]
        if not filtered:
            return "No backup for this application"

        lines = ["*Backups:*", ""]
        for item in filtered:
            lines.append(f"- {item.application_name} status={item.status} local_id={item.id}")
            if item.provider_backup_id:
                lines.append(f"  provider_id={item.provider_backup_id}")
            lines.append(f"  created={item.created_at.strftime('%Y-%m-%d %H:%M')}")
            if item.error:
                lines.append(f"  error={item.error}")
        return "\n".join(lines)

    def get_backup_schedule(self) -> str:
        return (
            "*Backup Settings*\n"
            f"enabled={self.backup_config['auto_backup_enabled']}\n"
            f"schedule={self.backup_config['backup_schedule']}\n"
            f"retention_days={self.backup_config['retention_days']}"
        )

    async def execute_task(self, task: ScheduledTask) -> bool:
        task.last_run = datetime.now()
        task.last_status = TaskStatus.RUNNING
        logger.info("Executing task: %s", task.name)

        try:
            if task.task_type == TaskType.BACKUP:
                apps = self.api.get_applications()
                for app in apps:
                    await self.create_backup(app.get("id", ""), app.get("name", ""))
            elif task.task_type == TaskType.HEALTH_CHECK:
                apps = self.api.get_applications()
                for app in apps:
                    self.api.get_application_status(app.get("id", ""))
            elif task.task_type == TaskType.CLEANUP:
                await self.cleanup_old_backups()

            task.last_status = TaskStatus.COMPLETED
            task.next_run = self._calculate_next_run(task.cron_expression, base=task.last_run)
            return True
        except Exception as exc:
            task.last_status = TaskStatus.FAILED
            logger.error("Task error: %s", exc)
            task.next_run = self._calculate_next_run(task.cron_expression, base=datetime.now())
            return False

    async def cleanup_old_backups(self):
        retention_days = self.backup_config["retention_days"]
        cutoff = datetime.now() - timedelta(days=retention_days)
        old_backups = [b for b in self.backups if b.created_at < cutoff]

        for backup in old_backups:
            try:
                provider_id = backup.provider_backup_id or backup.id
                self.api.delete_backup(backup.application_id, provider_id)
            except Exception as exc:
                logger.error("Backup delete error: %s", exc)

        return len(old_backups)

    async def start_scheduler(self):
        self.running = True
        logger.info("Scheduler Agent started")
        self._setup_default_tasks()

        while self.running:
            try:
                now = datetime.now()
                for task in self.scheduled_tasks:
                    if not task.enabled:
                        continue
                    if task.next_run is None:
                        task.next_run = self._calculate_next_run(task.cron_expression, base=now)
                    if task.next_run and now >= task.next_run:
                        await self.execute_task(task)
                        for callback in self.callbacks:
                            try:
                                callback(task)
                            except Exception as exc:
                                logger.error("Callback error: %s", exc)

                await asyncio.sleep(30)
            except Exception as exc:
                logger.error("Scheduler loop error: %s", exc)
                await asyncio.sleep(5)

    def _setup_default_tasks(self):
        if self.backup_config["auto_backup_enabled"] and not self.get_task_by_name("automatic_backup"):
            self.add_task(
                name="automatic_backup",
                cron=self.backup_config["backup_schedule"],
                command="backup_all",
                task_type=TaskType.BACKUP,
            )

        if not self.get_task_by_name("daily_health_check"):
            self.add_task(
                name="daily_health_check",
                cron="0 6 * * *",
                command="health_check",
                task_type=TaskType.HEALTH_CHECK,
            )

        if not self.get_task_by_name("weekly_cleanup"):
            self.add_task(
                name="weekly_cleanup",
                cron="0 3 * * 0",
                command="cleanup",
                task_type=TaskType.CLEANUP,
            )

    def _calculate_next_run(self, cron_expression: str, base: Optional[datetime] = None) -> Optional[datetime]:
        base = base or datetime.now()
        try:
            return croniter(cron_expression, base).get_next(datetime)
        except Exception:
            return None

    def get_task_by_name(self, name: str) -> Optional[ScheduledTask]:
        for task in self.scheduled_tasks:
            if task.name.lower() == name.lower():
                return task
        return None

    def stop_scheduler(self):
        self.running = False
        logger.info("Scheduler Agent stopped")

    def register_callback(self, callback: Callable):
        self.callbacks.append(callback)


scheduler_agent = SchedulerAgent()


def get_scheduler_agent() -> SchedulerAgent:
    return scheduler_agent
