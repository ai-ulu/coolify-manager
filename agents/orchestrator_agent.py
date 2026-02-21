"""
Orchestrator agent for natural-language operations.
Coordinates role-based sub-agents and enforces approval gates for risky actions.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional

import requests

from config import AUTONOMOUS_CONFIG, BACKUP_CONFIG, COOLIFY_CONFIG, LLM_CONFIG, TELEGRAM_CONFIG
from coolify_api import CoolifyAPI
from agents.coordinator_agent import get_coordinator
from agents.monitoring_agent import get_monitoring_agent
from agents.scheduler_agent import get_scheduler_agent

logger = logging.getLogger(__name__)


@dataclass
class ParsedIntent:
    action: str
    app_name: str = ""
    raw: str = ""


@dataclass
class PendingApproval:
    approval_id: str
    action: str
    app_id: str = ""
    app_name: str = ""
    requested_by: int = 0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class AgentResult:
    text: str
    handled: bool = True
    requires_approval: bool = False
    approval_id: str = ""


class MonitoringSubAgent:
    def __init__(self):
        self.monitoring = get_monitoring_agent()
        self.coordinator = get_coordinator()

    async def full_report(self) -> str:
        await self.coordinator.check_all_servers()
        server_summary = self.coordinator.get_unified_status()
        server_list = self.coordinator.list_servers()
        metrics = self.monitoring.format_metrics()
        alerts = self.monitoring.format_alerts()
        return f"{server_summary}\n\n{metrics}\n\n{alerts}\n\n{server_list}"


class SecuritySubAgent:
    def config_report(self) -> str:
        coolify_url = COOLIFY_CONFIG.get("url", "n/a")
        api_key_set = bool(COOLIFY_CONFIG.get("api_key"))
        bot_token_set = bool(TELEGRAM_CONFIG.get("bot_token"))
        llm_key_set = bool(LLM_CONFIG.get("api_key"))
        llm_url = LLM_CONFIG.get("api_base", "n/a")
        return (
            "Yapilandirma Raporu:\n"
            f"- Coolify URL: {coolify_url}\n"
            f"- Coolify API key: {'set' if api_key_set else 'missing'}\n"
            f"- Telegram token: {'set' if bot_token_set else 'missing'}\n"
            f"- LiteLLM URL: {llm_url}\n"
            f"- LiteLLM key: {'set' if llm_key_set else 'missing'}\n"
            f"- Allowed users: {len(TELEGRAM_CONFIG.get('allowed_users', []))}\n"
            f"- Admin users: {len(TELEGRAM_CONFIG.get('admin_users', []))}\n"
            f"- Backup auto: {BACKUP_CONFIG.get('auto_backup_enabled')}\n"
            f"- Backup cron: {BACKUP_CONFIG.get('backup_schedule')}\n"
            f"- Auto cleanup: {AUTONOMOUS_CONFIG.get('cleanup_enabled')}"
        )


class DeploySubAgent:
    def __init__(self):
        self.api = CoolifyAPI()

    def find_app(self, app_name: str) -> Optional[Dict]:
        if not app_name:
            return None
        apps = self.api.get_applications()
        target = app_name.lower().strip()
        exact = next((a for a in apps if a.get("name", "").lower() == target), None)
        if exact:
            return exact
        return next((a for a in apps if target in a.get("name", "").lower()), None)

    def list_apps(self) -> str:
        apps = self.api.get_applications()
        if not apps:
            return "Uygulama bulunamadi."
        lines = ["Uygulamalar:"]
        for app in apps[:20]:
            lines.append(f"- {app.get('name', 'unknown')} [{app.get('status', 'unknown')}]")
        return "\n".join(lines)

    def execute(self, action: str, app_id: str) -> Dict:
        if action == "deploy_app":
            return self.api.deploy_application(app_id)
        if action == "restart_app":
            return self.api.restart_application(app_id)
        if action == "start_app":
            return self.api.start_application(app_id)
        if action == "stop_app":
            return self.api.stop_application(app_id)
        return {"error": f"unsupported action: {action}"}


class BackupSubAgent:
    def __init__(self):
        self.scheduler = get_scheduler_agent()
        self.deploy = DeploySubAgent()

    async def create_backup_for_app(self, app_name: str) -> str:
        app = self.deploy.find_app(app_name)
        if not app:
            return "Uygulama bulunamadi."
        backup = await self.scheduler.create_backup(str(app.get("id")), app.get("name", ""))
        return f"Backup status={backup.status}, id={backup.id}"

    async def create_backup_for_all(self) -> str:
        apps = CoolifyAPI().get_applications()
        for app in apps[:10]:
            await self.scheduler.create_backup(str(app.get("id")), app.get("name", ""))
        return f"Backup istendi: {min(len(apps), 10)} uygulama"

    def list_backups(self) -> str:
        return self.scheduler.list_backups()


class ReporterSubAgent:
    def approval_message(self, action: str, app_name: str, approval_id: str) -> str:
        action_text = {
            "deploy_app": "deploy",
            "restart_app": "restart",
            "start_app": "start",
            "stop_app": "stop",
        }.get(action, action)
        return (
            f"Onay gerekli: `{app_name}` icin `{action_text}`\n"
            f"Onaylamak icin: /approve {approval_id}\n"
            f"Iptal icin: /reject {approval_id}"
        )


class OrchestratorAgent:
    def __init__(self):
        self.deploy = DeploySubAgent()
        self.monitoring = MonitoringSubAgent()
        self.backup = BackupSubAgent()
        self.security = SecuritySubAgent()
        self.reporter = ReporterSubAgent()
        self.pending_approvals: Dict[str, PendingApproval] = {}
        self.approval_ttl = timedelta(minutes=10)
        self.llm_enabled = bool(LLM_CONFIG.get("enabled") and LLM_CONFIG.get("api_base"))

    async def handle_user_text(self, user_id: int, text: str, is_admin: bool) -> AgentResult:
        intent = self._parse_intent(text)
        action = intent.action

        if action == "unknown":
            return AgentResult("Anlamadim. /help ile komutlari gorebilirsin.", handled=False)
        if action == "help":
            return AgentResult(
                "Dogal dil ornekleri:\n"
                "- coolify sunucu durumunu raporla\n"
                "- uygulamalari listele\n"
                "- api uygulamasini restart et\n"
                "- tum uygulamalari yedekle\n"
                "- yapilandirma raporu ver"
            )
        if action == "status_report":
            return AgentResult(await self.monitoring.full_report())
        if action == "status_and_config":
            report = await self.monitoring.full_report()
            return AgentResult(f"{report}\n\n{self.security.config_report()}")
        if action == "security_report":
            return AgentResult(self.security.config_report())
        if action == "list_apps":
            return AgentResult(self.deploy.list_apps())
        if action == "backup_all":
            if not is_admin:
                return AgentResult("Bu islem admin yetkisi gerektirir.")
            return AgentResult(await self.backup.create_backup_for_all())
        if action == "backup_app":
            if not is_admin:
                return AgentResult("Bu islem admin yetkisi gerektirir.")
            if not intent.app_name:
                return AgentResult("Hangi uygulama? Ornek: `api uygulamasini yedekle`")
            return AgentResult(await self.backup.create_backup_for_app(intent.app_name))
        if action == "list_backups":
            return AgentResult(self.backup.list_backups())

        if action in {"deploy_app", "restart_app", "start_app", "stop_app"}:
            if not is_admin:
                return AgentResult("Bu islem admin yetkisi gerektirir.")
            if not intent.app_name:
                return AgentResult("Uygulama adini belirt. Ornek: `api uygulamasini restart et`")
            app = self.deploy.find_app(intent.app_name)
            if not app:
                return AgentResult("Uygulama bulunamadi.")

            approval = self._create_approval(
                action=action,
                app_id=str(app.get("id")),
                app_name=str(app.get("name", intent.app_name)),
                requested_by=user_id,
            )
            return AgentResult(
                text=self.reporter.approval_message(action, approval.app_name, approval.approval_id),
                requires_approval=True,
                approval_id=approval.approval_id,
            )

        return AgentResult("Anlamadim. /help ile komutlari gorebilirsin.", handled=False)

    def approve(self, approval_id: str, user_id: int, is_admin: bool) -> str:
        self._cleanup_expired_approvals()
        approval = self.pending_approvals.get(approval_id)
        if not approval:
            return "Gecersiz veya zamani dolmus onay."
        if not is_admin and approval.requested_by != user_id:
            return "Bu onayi verme yetkin yok."

        result = self.deploy.execute(approval.action, approval.app_id)
        del self.pending_approvals[approval_id]
        if "error" in result:
            return f"Islem basarisiz: {result.get('error')}"
        return f"Islem baslatildi: {approval.action} -> {approval.app_name}"

    def reject(self, approval_id: str, user_id: int, is_admin: bool) -> str:
        self._cleanup_expired_approvals()
        approval = self.pending_approvals.get(approval_id)
        if not approval:
            return "Gecersiz veya zamani dolmus onay."
        if not is_admin and approval.requested_by != user_id:
            return "Bu onayi reddetme yetkin yok."
        del self.pending_approvals[approval_id]
        return f"Islem iptal edildi: {approval.action} -> {approval.app_name}"

    def list_pending(self) -> str:
        self._cleanup_expired_approvals()
        if not self.pending_approvals:
            return "Bekleyen onay yok."
        lines = ["Bekleyen onaylar:"]
        for approval in self.pending_approvals.values():
            lines.append(f"- {approval.approval_id}: {approval.action} -> {approval.app_name}")
        return "\n".join(lines)

    def _create_approval(self, action: str, app_id: str, app_name: str, requested_by: int) -> PendingApproval:
        approval_id = secrets.token_hex(3)
        item = PendingApproval(
            approval_id=approval_id,
            action=action,
            app_id=app_id,
            app_name=app_name,
            requested_by=requested_by,
        )
        self.pending_approvals[approval_id] = item
        self._cleanup_expired_approvals()
        return item

    def _cleanup_expired_approvals(self):
        now = datetime.now()
        for approval_id, approval in list(self.pending_approvals.items()):
            if now - approval.created_at > self.approval_ttl:
                del self.pending_approvals[approval_id]

    def _parse_intent(self, text: str) -> ParsedIntent:
        stripped = text.strip()
        lowered = stripped.lower()
        lowered_norm = self._normalize_turkish(lowered)

        if self.llm_enabled:
            llm_intent = self._parse_with_llm(stripped)
            if llm_intent:
                return llm_intent

        app_name = self._extract_app_name(lowered_norm)
        if any(k in lowered_norm for k in ["yardim", "help", "komut"]):
            return ParsedIntent(action="help", app_name=app_name, raw=stripped)
        if (
            any(k in lowered_norm for k in ["sunucu", "server", "coolify"])
            and any(k in lowered_norm for k in ["durum", "status", "kontrol", "rapor"])
            and any(k in lowered_norm for k in ["yapilandirma", "ayar", "config"])
        ):
            return ParsedIntent(action="status_and_config", app_name=app_name, raw=stripped)
        if any(k in lowered_norm for k in ["yapilandirma", "ayar", "config"]):
            return ParsedIntent(action="security_report", app_name=app_name, raw=stripped)
        if all(k in lowered_norm for k in ["sunucu", "rapor"]) or "durum" in lowered_norm or "status" in lowered_norm:
            return ParsedIntent(action="status_report", app_name=app_name, raw=stripped)
        if any(k in lowered_norm for k in ["uygulama", "app"]) and any(k in lowered_norm for k in ["liste", "list"]):
            return ParsedIntent(action="list_apps", app_name=app_name, raw=stripped)
        if any(k in lowered_norm for k in ["backup", "yedek"]) and any(k in lowered_norm for k in ["liste", "list"]):
            return ParsedIntent(action="list_backups", app_name=app_name, raw=stripped)
        if any(k in lowered_norm for k in ["tum", "hepsi"]) and any(k in lowered_norm for k in ["backup", "yedek"]):
            return ParsedIntent(action="backup_all", app_name=app_name, raw=stripped)
        if any(k in lowered_norm for k in ["backup", "yedek"]):
            return ParsedIntent(action="backup_app", app_name=app_name, raw=stripped)
        if any(k in lowered_norm for k in ["deploy", "yayinla"]):
            return ParsedIntent(action="deploy_app", app_name=app_name, raw=stripped)
        if any(k in lowered_norm for k in ["restart", "yeniden baslat"]):
            return ParsedIntent(action="restart_app", app_name=app_name, raw=stripped)
        if any(k in lowered_norm for k in ["durdur", "stop"]):
            return ParsedIntent(action="stop_app", app_name=app_name, raw=stripped)
        if any(k in lowered_norm for k in ["baslat", "start"]):
            return ParsedIntent(action="start_app", app_name=app_name, raw=stripped)

        return ParsedIntent(action="unknown", app_name=app_name, raw=stripped)

    def _parse_with_llm(self, text: str) -> Optional[ParsedIntent]:
        api_base = LLM_CONFIG.get("api_base", "").rstrip("/")
        api_key = LLM_CONFIG.get("api_key", "")
        model = LLM_CONFIG.get("model", "gpt-4o-mini")
        if not api_base:
            return None

        prompt = (
            "Convert user request to JSON with keys action and app_name. "
            "Allowed actions: help,status_report,status_and_config,security_report,list_apps,list_backups,"
            "backup_all,backup_app,deploy_app,restart_app,start_app,stop_app,unknown. "
            "If unknown set action=unknown. app_name can be empty."
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = requests.post(f"{api_base}/chat/completions", json=payload, headers=headers, timeout=12)
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            parsed = json.loads(content)
            action = str(parsed.get("action", "unknown"))
            app_name = str(parsed.get("app_name", "")).strip()
            if not action:
                action = "unknown"
            return ParsedIntent(action=action, app_name=app_name, raw=text)
        except Exception as exc:
            logger.debug("LLM intent parse failed, fallback to heuristics: %s", exc)
            return None

    def _extract_app_name(self, text: str) -> str:
        text = text.strip()
        quoted = re.search(r"'([^']+)'|\"([^\"]+)\"", text)
        if quoted:
            return quoted.group(1) or quoted.group(2) or ""
        patterns = [
            r"(?:uygulama|app)\s+([a-zA-Z0-9._-]+)",
            r"([a-zA-Z0-9._-]+)\s+uygulamasini",
            r"(?:restart|deploy|start|stop|yedekle)\s+([a-zA-Z0-9._-]+)",
        ]
        reserved = {"et", "yap", "yapalim", "lutfen"}
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = match.group(1).strip()
                if value and value not in reserved:
                    return value
        return ""

    def _normalize_turkish(self, text: str) -> str:
        table = str.maketrans(
            {
                "ç": "c",
                "ğ": "g",
                "ı": "i",
                "ö": "o",
                "ş": "s",
                "ü": "u",
            }
        )
        return text.translate(table)


orchestrator = OrchestratorAgent()


def get_orchestrator() -> OrchestratorAgent:
    return orchestrator
