# Task Design

## Phase 0 - Baseline Hardening
- [x] Remove hardcoded credentials from code paths.
- [x] Convert config to env-first model.
- [x] Fix API header key isolation.

## Phase 1 - Runtime Correctness
- [x] Fix imports so runtime starts with current repo layout.
- [x] Ensure startup creates required directories.
- [x] Remove Telegram command collision (`/start` vs app-start).

## Phase 2 - Control Plane Safety
- [x] Enforce Telegram RBAC (`allowed_users`, `admin_users`).
- [x] Gate mutating commands behind admin check.
- [x] Keep read commands available to allowed users.

## Phase 3 - Automation Safety
- [x] Replace naive scheduler timing with croniter next-run calculation.
- [x] Avoid immediate first-run execution.
- [x] Restrict autonomous cleanup to explicit configured paths.
- [x] Disable cleanup by default.

## Phase 4 - Dependency and Deploy Templates
- [x] Add missing runtime dependencies.
- [x] Convert compose/service templates to environment-driven secrets.

## Phase 5 - Verification
- [x] Static import smoke check (`python -c "import run"`).
- [x] Runtime smoke (`python run.py` with mock/real env).
- [x] Telegram RBAC smoke with one allowed and one blocked user.
- [x] Natural-language status/config smoke in Telegram.
- [x] Natural-language mutating command must require approval token.

## Phase 6 - Orchestrator Expansion
- [x] Add `OrchestratorAgent` with role-based sub-agents.
- [x] Add approval queue with TTL for risky actions.
- [x] Add Telegram commands `/pending`, `/approve`, `/reject`.
- [x] Add LiteLLM optional intent routing with heuristic fallback.
- [x] Fix Turkish natural-language app name parsing (`uygulamasini/uygulamasını`).

## Phase 7 - Release
- [x] Commit changes with clear scope.
- [x] Push to target branch.
- [x] Trigger Coolify deployment.
- [x] Validate app health and logs post-deploy.
