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
- [ ] Static import smoke check (`python -c "import run"`).
- [ ] Runtime smoke (`python run.py` with mock/real env).
- [ ] Telegram RBAC smoke with one allowed and one blocked user.

## Phase 6 - Release
- [ ] Commit changes with clear scope.
- [ ] Push to target branch.
- [ ] Trigger Coolify deployment.
- [ ] Validate app health and logs post-deploy.
