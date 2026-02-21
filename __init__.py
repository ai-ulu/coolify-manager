"""
Coolify Multi-Agent Manager
Ana modül
"""

from config import COOLIFY_CONFIG, TELEGRAM_CONFIG, THRESHOLDS, BACKUP_CONFIG
from coolify_api import CoolifyAPI, get_api
from agents.monitoring_agent import MonitoringAgent, get_monitoring_agent
from agents.scheduler_agent import SchedulerAgent, get_scheduler_agent
from agents.coordinator_agent import MultiServerCoordinator, get_coordinator
from telegram_bot import CoolifyBot, create_bot, get_bot

__version__ = "1.0.0"
__all__ = [
    "COOLIFY_CONFIG",
    "TELEGRAM_CONFIG", 
    "THRESHOLDS",
    "BACKUP_CONFIG",
    "CoolifyAPI",
    "get_api",
    "MonitoringAgent",
    "get_monitoring_agent",
    "SchedulerAgent",
    "get_scheduler_agent",
    "MultiServerCoordinator",
    "get_coordinator",
    "CoolifyBot",
    "create_bot",
    "get_bot",
]
