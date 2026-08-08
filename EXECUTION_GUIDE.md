# EXECUTION_GUIDE.md — How to Run This Framework

This is a step-by-step walkthrough to get `pw-framework` running locally,
in Docker, and in CI — including **every single place** a credential,
account, or secret needs to be filled in. Nothing below is guessed; it's
traced directly from the code (`src/core/config.py`, `.env.example`, and
every `.github/workflows/*.yml` file).

---

## Part 1 — Local Setup

### 1.1 Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
  (`curl -LsSf https://astral.sh/uv/install.sh | sh`, or `pip install uv`)
- Node not required (Playwright installs its own browser binaries)

### 1.2 Install dependencies

```bash
cd pw-framework
uv sync
```

This creates a `.venv/` and installs every dependency pinned in `uv.lock`
in a few seconds (verified: ~6.6s for a full 60-package sync in this build).
Use `uv sync --frozen` in CI/CD to guarantee the lockfile is used exactly
as-is, with no re-resolution.

### 1.3 Install Playwright browser binaries

Installing the `playwright` Python package does **not** download the actual
browsers — this is a separate required step:

```bash
uv run playwright install --with-deps chromium firefox webkit
```

### 1.4 Set up your `.env` file — ⚠️ Credentials go here

```bash
cp .env.example .env
```

Then open `.env` and fill in real values. Here is exactly what each line
does and where it flows to:

| Variable | Used for | Where it's read | Required? |
|---|---|---|---|
| `TEST_ENV` | Selects which block of `config/environments.yaml` to use (`qa`/`staging`/`prod`) | `src/core/config.py` | Yes — defaults to `qa` if unset |
| `APP_USERNAME` | Login username for the UI app under test (SauceDemo / OrangeHRM / Banking) | `src/core/config.py` → `Config.app_username` → used in `LoginPage.login()` calls in tests | Yes, for any UI test |
| `APP_PASSWORD` | Login password for the UI app under test | Same as above | Yes, for any UI test |
| `API_TOKEN` | Bearer token if your API under test requires one | `src/core/config.py` → `Config.api_token` → pass into `BearerTokenAuth` when constructing `APIClient` | Only if API requires auth (the demo `reqres.in` API used in Chapter 3 does not) |
| `API_CLIENT_ID` / `API_CLIENT_SECRET` | OAuth2 client-credentials grant, if your real API uses it | Passed manually into `OAuth2ClientCredentialsAuth(...)` — see `src/api/auth_strategies.py` | Only if using OAuth2 auth strategy |
| `DB_USER` / `DB_PASSWORD` | Database login for `DBClient` | `src/core/config.py` → `DBConfig.user`/`.password` → `src/db/db_client.py` connection string | Only if running DB-layer tests against a real (non-SQLite) database |
| `SLACK_WEBHOOK_URL` | Slack notifications from CI on failure | Referenced in `.github/workflows/pr-validation.yml`, `release-pipeline.yml`, `scheduled-smoke.yml` | Only needed in CI, not local runs |
| `TEAMS_WEBHOOK_URL` | Teams notifications from CI on failure | Referenced in `.github/workflows/nightly-regression.yml` | Only needed in CI |
| `VAULT_ADDR` / `VAULT_TOKEN` | Placeholder for HashiCorp Vault integration (conceptual — not wired into any code yet) | Not currently consumed anywhere | Optional / future extension point |

**Where these show up in `config/environments.yaml`:** the `base_url`,
`api_base_url`, and `db.host/port/name` values are non-secret and already
filled in with demo values (SauceDemo, reqres.in, placeholder DB host names).
You will need to **replace these with your real target URLs** once you're
testing your own application instead of the public demo sites:

```yaml
# config/environments.yaml
qa:
  base_url: "https://www.saucedemo.com"        # ← replace with your app's QA URL
  api_base_url: "https://reqres.in/api"          # ← replace with your API's QA URL
  db:
    host: "qa-db.internal.example.com"           # ← replace with your real DB host
```

### 1.5 Run tests

```bash
# Smoke tests only, parallel
uv run pytest -m smoke -n auto

# Full regression
uv run pytest -m regression -n auto

# API tests only (no browser needed)
uv run pytest -m api

# Specific environment override, without editing .env
uv run pytest -m smoke --env staging

# Reuse a saved login session instead of logging in every test
uv run pytest -m regression --use-storage-state
```

### 1.6 View reports

- HTML report: `reports/html/report.html`
- Allure results: `reports/allure-results/` — run `allure serve reports/allure-results` if you have the Allure CLI installed, to view an interactive report
- JUnit XML: `reports/junit/results.xml`
- Logs: `logs/automation.log` (rotating, 10MB × 5 backups)
- Failure screenshots: `reports/screenshots/`
- Failure traces: `reports/traces/` — open with `playwright show-trace <file>.zip`

---

## Part 2 — Running with Docker

### 2.1 Prerequisites

- Docker + Docker Compose installed and the daemon running

### 2.2 Credentials for Docker

`docker-compose.yml` reads the same environment variables as local runs,
but via shell environment or a `.env` file **in the same directory as
docker-compose.yml** (Docker Compose auto-loads `.env` if present):

```bash
# .env in repo root, same file as Part 1.4 — Compose will pick it up automatically
TEST_ENV=qa
BASE_URL=https://www.saucedemo.com
API_BASE_URL=https://reqres.in/api
DB_USER=postgres
DB_PASSWORD=postgres
```

Note: the local Postgres service defined in `docker-compose.yml` (`db:`)
ships with hardcoded demo credentials (`postgres`/`postgres`) for local dev
convenience only — **never point this at a real staging/prod database
without changing that.**

### 2.3 Build and run

```bash
docker compose build
docker compose up automation
```

### 2.4 View Allure report from Docker

```bash
docker compose up allure-report
# then open http://localhost:5050
```

---

## Part 3 — CI Setup (GitHub Actions) — ⚠️ Secrets go here

All 5 workflows use `astral-sh/setup-uv@v8.1.0` to install uv on the
runner (with `enable-cache: true` so the dependency cache persists between
runs), followed by `uv sync --locked --all-extras --dev` to install the
exact locked dependency set. No manual `pip install uv` step or extra
package-manager bootstrapping is needed — this is handled entirely by
that one action in every workflow.

All 5 workflows in `.github/workflows/` read credentials from **GitHub
repository secrets**, not from `.env` (which is git-ignored and never
present in CI). You must add these under:

**GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Used in workflow(s) | Purpose |
|---|---|---|
| `APP_USERNAME` | `pr-validation.yml`, `nightly-regression.yml`, `release-pipeline.yml`, `manual-run.yml` | Login credential for UI tests against QA/staging |
| `APP_PASSWORD` | Same as above | Login credential (password) |
| `DB_USER` | `nightly-regression.yml` | Database username for DB-layer regression tests |
| `DB_PASSWORD` | `nightly-regression.yml` | Database password |
| `PROD_READONLY_USERNAME` | `scheduled-smoke.yml` | **Separate, read-only** account for prod sanity checks — deliberately not the same as `APP_USERNAME` so prod checks can never accidentally write/mutate data |
| `PROD_READONLY_PASSWORD` | `scheduled-smoke.yml` | Password for the above |
| `SLACK_WEBHOOK_URL` | `pr-validation.yml`, `release-pipeline.yml`, `scheduled-smoke.yml` | Slack incoming webhook URL for failure notifications |
| `TEAMS_WEBHOOK_URL` | `nightly-regression.yml` | Microsoft Teams incoming webhook URL for nightly failure alerts |
| `GITHUB_TOKEN` | `nightly-regression.yml` | **Auto-provided by GitHub Actions** — you do not need to create this one manually, it exists by default in every workflow run |

### 3.1 How to get a Slack webhook URL
Slack → your workspace → Apps → search "Incoming Webhooks" → add to a
channel → copy the generated URL → paste as the `SLACK_WEBHOOK_URL` secret.

### 3.2 How to get a Teams webhook URL
Teams channel → "..." menu → Connectors → Incoming Webhook → configure →
copy the generated URL → paste as the `TEAMS_WEBHOOK_URL` secret.

### 3.3 Verifying secrets are wired correctly
Trigger the **Manual Test Run** workflow (`workflow_dispatch` in
`manual-run.yml`) from the Actions tab with `marker=smoke` — this is the
fastest way to confirm secrets resolve correctly without waiting for a
scheduled run.

---

## Part 4 — Adding a New Environment (e.g., a real staging server)

1. Add a new block to `config/environments.yaml` (copy the `staging:` block
   as a template)
2. Point `base_url`, `api_base_url`, and `db.host/port/name` at your real
   infrastructure
3. If that environment needs different credentials than QA, either:
   - Use the same `.env` variables (they apply across all `TEST_ENV`
     values — same `APP_USERNAME`/`APP_PASSWORD` used everywhere), or
   - Extend `src/core/config.py` if you need per-environment credential
     separation (e.g., `STAGING_APP_PASSWORD` instead of a shared
     `APP_PASSWORD`) — not built in by default, since most teams use one
     shared automation account per environment tier already

---

## Part 5 — Common First-Run Issues

| Symptom | Fix |
|---|---|
| `FileNotFoundError: Missing config file` | You're not running pytest from the repo root — `config/environments.yaml` is resolved relative to the repo root |
| Browser launch fails / "Executable doesn't exist" | You skipped step 1.3 — run `playwright install --with-deps` |
| Login tests fail immediately | `.env` wasn't copied/filled in (step 1.4), or `APP_USERNAME`/`APP_PASSWORD` are still the placeholder demo values but you're pointing `base_url` at your own app |
| DB tests fail to connect | `DB_USER`/`DB_PASSWORD` unset — the SQLite examples in the codebase don't need these, but Postgres/MySQL/etc. do |
| CI workflow fails with a masked/empty credential error | The GitHub secret name doesn't exactly match what the workflow YAML references — check Part 3's table for exact spelling |

For deeper failure-mode debugging, see `docs/troubleshooting.md`.
