#!/usr/bin/env python3
"""
Coolify manager entrypoint.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
Path("logs").mkdir(parents=True, exist_ok=True)

from config import TELEGRAM_CONFIG
from coolify_api import get_api
from agents.coordinator_agent import get_coordinator
from agents.monitoring_agent import get_monitoring_agent
from agents.scheduler_agent import get_scheduler_agent
from telegram_bot import create_bot


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/coolify_manager.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class CoolifyManager:
    def __init__(self):
        self.monitoring = get_monitoring_agent()
        self.scheduler = get_scheduler_agent()
        self.coordinator = get_coordinator()
        self.bot = None
        self.running = False
        self.tasks = []

    async def start(self):
        self.running = True
        logger.info("=" * 50)
        logger.info("Coolify Multi-Agent system starting")
        logger.info("=" * 50)

        api = get_api()
        logger.info("Testing Coolify API connection")
        if api.test_connection():
            logger.info("Coolify connection OK")
        else:
            logger.warning("Coolify connection failed, check configuration")

        bot_token = TELEGRAM_CONFIG.get("bot_token")
        if bot_token:
            logger.info("Starting Telegram bot")
            self.bot = create_bot(bot_token)
        else:
            logger.info("Telegram bot token not set, bot disabled")

        logger.info("Starting agents")
        self.tasks.append(asyncio.create_task(self.monitoring.start_monitoring()))
        logger.info("Monitoring agent active")

        self.tasks.append(asyncio.create_task(self.scheduler.start_scheduler()))
        logger.info("Scheduler agent active")

        await self.coordinator.check_all_servers()
        logger.info("Registered servers: %s", len(self.coordinator.servers))

        logger.info("=" * 50)
        logger.info("System active")
        logger.info("=" * 50)

        if self.bot:
            # Bot polling is blocking; run it in a worker thread.
            try:
                await asyncio.to_thread(self.bot.run)
            except Exception as exc:
                logger.exception("Telegram bot crashed, continuing without bot: %s", exc)
                while self.running:
                    await asyncio.sleep(5)
        else:
            while self.running:
                await asyncio.sleep(5)

    async def stop(self):
        self.running = False
        logger.info("Shutting down")

        self.monitoring.stop_monitoring()
        self.scheduler.stop_scheduler()
        for task in self.tasks:
            task.cancel()

        logger.info("All agents stopped")


async def main():
    manager = CoolifyManager()

    def signal_handler(sig, frame):
        logger.info("Signal received, stopping")
        asyncio.create_task(manager.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await manager.start()


if __name__ == "__main__":
    asyncio.run(main())
