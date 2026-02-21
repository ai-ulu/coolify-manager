# Blueprint: Coolify Autonomous Manager

## 1) Mission
Build a secure autonomous operations controller that can monitor, alert, and execute safe remediation actions on Coolify-managed resources.

## 2) Scope
- Single primary Coolify endpoint with optional multi-server expansion.
- Telegram as control plane and alert channel.
- Autonomous actions for health recovery, backup scheduling, and constrained cleanup.

## 3) Non-Goals
- Full AI-based root-cause remediation without operator guardrails.
- Arbitrary command execution on hosts.
- Unbounded destructive actions.

## 4) Architecture
- `run.py`: bootstrap and lifecycle manager.
- `coolify_api.py`: HTTP client for Coolify API.
- `agents/monitoring_agent.py`: host metric loop + threshold alerts.
- `agents/scheduler_agent.py`: cron-based job orchestration and backups.
- `agents/autonomous_agent.py`: policy-driven remediation with cooldown.
- `telegram_bot.py`: operator interface and RBAC gate.
- `notifications.py`: pluggable outbound channels.

## 5) Security Model
- Secrets only via environment variables.
- Telegram RBAC:
  - `allowed_users`: read/observe commands.
  - `admin_users`: mutating commands (deploy/start/stop/restart/backup/restore).
- Cleanup operations are disabled by default and restricted to explicit paths.

## 6) Operational Policies
- Backups scheduled by cron, never immediate-on-start.
- Auto-heal only after repeated health-check failures.
- Cooldowns applied per action+target key.
- All actions are logged with timestamp and reason.

## 7) Deploy Model
- Container image from this repo.
- Runtime env vars injected by Coolify.
- No secrets committed in code, compose, or service files.

## 8) Definition of Done
- System starts cleanly.
- RBAC enforced on Telegram commands.
- Scheduler computes next run from cron expressions.
- No hardcoded credentials in tracked files.
- Basic smoke checks pass.
