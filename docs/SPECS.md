# Specs

## Functional Requirements

### FR-1 Startup
- App must boot via `python run.py`.
- Must create required runtime directories (`logs`, `data`) if missing.

### FR-2 Coolify API Client
- Must support endpoint URL and API key per instance.
- Request headers must use instance key, not global singleton secret.
- Must return structured error payloads (`{"error": "..."}`) on failure.

### FR-3 Monitoring
- Collect CPU/RAM/Disk/Network metrics periodically.
- Generate warnings/critical alerts according to thresholds.
- Work on Linux and Windows path/loadavg differences.

### FR-4 Scheduler
- Parse cron expressions correctly.
- Do not execute all tasks immediately on first startup.
- Persist in-memory execution history for current runtime.

### FR-5 Backups
- Trigger backup via Coolify API.
- Track both local backup record id and provider backup id.
- Restore/delete operations should prefer provider backup id when available.

### FR-6 Autonomous Remediation
- Health-check apps and auto-heal after repeated failures.
- Disk cleanup disabled by default.
- Cleanup only in configured explicit paths and age-based retention.

### FR-7 Telegram Control Plane
- RBAC checks on each command:
  - Read commands require `allowed_users` (if configured).
  - Mutating commands require `admin_users` (if configured).
- No duplicate command routing conflicts.

### FR-8 Notifications
- Telegram bot token and chat ids must come from env.
- Missing token should disable send path gracefully.

## Non-Functional Requirements

### NFR-1 Security
- Zero hardcoded secrets in source-controlled files.

### NFR-2 Reliability
- Event loops should survive transient API/network errors.

### NFR-3 Maintainability
- Modules should import directly without requiring absent package layout.

### NFR-4 Deployability
- Compose/systemd templates must consume env values.

## Environment Variables (minimum)
- `COOLIFY_API_URL`
- `COOLIFY_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USERS`
- `TELEGRAM_ADMIN_USERS`
- `BACKUP_AUTO_ENABLED`
- `BACKUP_SCHEDULE`
- `AUTO_CLEANUP_ENABLED`
- `AUTO_CLEANUP_PATHS`
