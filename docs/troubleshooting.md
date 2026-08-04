# Troubleshooting Guide

Organized by symptom. Each entry: what you'd actually see, the real cause,
and the fix — grounded in how this framework is built, not generic advice.

---

## "Tests pass locally, fail in CI"

**Symptom:** `pytest -m smoke` green on your laptop, red in GitHub Actions.

**Most likely causes, in order of frequency:**
1. **Headless vs headed rendering differences.** Some CSS (font rendering,
   scrollbars) differs between headed (your laptop, if `HEADLESS=false`
   locally) and headless (`HEADLESS=true` in CI). Fix: always develop with
   `HEADLESS=true` locally to match CI, or explicitly test both.
2. **Timing.** CI runners are typically slower/more resource-constrained
   than a dev laptop. A test that "just barely" passes locally due to a
   missing explicit wait will flake in CI. Fix: check for hardcoded
   `time.sleep()` calls (there shouldn't be any in this framework — every
   wait should go through `resilient_locator`'s built-in wait or Playwright's
   auto-wait) and confirm `navigation_timeout_ms` is generous enough.
3. **Missing environment secrets.** `APP_USERNAME`/`APP_PASSWORD` set as
   GitHub Secrets but a workflow YAML forgot to map them into `env:` for
   that specific job — `ConfigManager` silently falls back to empty string
   rather than crashing, so you get a confusing login failure instead of a
   clear "secret not found" error. Fix: check every workflow job that needs
   secrets actually lists them under `env:`.

---

## "ElementNotFoundError raised even though the element is visible in my
browser"

**Cause:** Either (a) the element is inside an iframe and you didn't use
`frame_locator()`, or (b) a fallback selector list is empty and the primary
selector's underlying `data-testid`/class genuinely changed. Check the log
— `resilient_locator` logs a WARNING when it falls back, so if you see
neither a warning nor success, the primary selector never matched at all
within its 2s attach timeout. Increase that timeout only as a last resort;
first check whether the element is genuinely still loading (network tab)
or if the app team renamed the attribute.

---

## "DB tests leave orphaned rows in the shared QA database"

**Cause:** Someone used `db.execute()` directly for test data setup instead
of `with db.transaction() as tx:`. `execute()` auto-commits — it's meant for
assertions that are supposed to actually persist (e.g., testing that an API
call correctly wrote to the DB). Any *setup* data a test creates for its own
use should go through the transaction context manager so it's guaranteed to
roll back.

**Fix:** grep the test suite for `db.execute(` calls used for setup rather
than verification, and migrate them to `db.transaction()`.

---

## "xdist workers report different numbers of tests / duplicate runs"

**Cause:** Usually a fixture with global mutable state — e.g., a
module-level list or dict that isn't properly scoped, so each xdist worker
process gets its own copy but tests assume shared state. Since xdist runs
in **separate processes**, not threads, nothing in Python memory is
actually shared between workers — that includes ConfigManager's singleton,
which is a *per-process* singleton, not a *per-suite* singleton. This is a
common misconception: "isn't ConfigManager a singleton, so it's shared?"
No — under xdist, each worker process gets its own singleton instance. This
is actually fine here since config is read-only and identical across
workers, but it would be a real bug if you tried to use a singleton to
coordinate *mutable* cross-worker state (e.g., a shared counter) — you'd
need a file lock, a DB row, or a proper external coordination mechanism for
that.

---

## "Allure report shows no screenshots/traces attached to failed tests"

**Cause chain to check, in order:**
1. Is `allure-pytest` actually installed? (`pip show allure-pytest`)
2. Is `--alluredir=reports/allure-results` actually in the pytest invocation
   (via `pytest.ini` addopts or explicit CLI flag)?
3. Is the `_attach_allure_artifacts()` helper in `conftest.py` actually
   being called? It's inside the `if test_failed:` branch — if the test
   technically errored during setup (not the test body itself), `rep_call`
   might not reflect that the way you expect; check `rep_setup.failed` too
   for setup-phase failures.
4. Was `allure` actually importable at attach time? The helper does a soft
   `try/except ImportError` — if the import silently fails, you'll get no
   error, just no attachment. Don't let that except block hide a real
   installation problem; log it during framework setup, not just swallow it.

---

## "Playwright says 'Executable doesn't exist' in Docker/CI"

**Cause:** `playwright install` (Python package metadata) and the actual
downloaded browser binaries are two different things — installing the
`playwright` pip package does NOT download Chromium/Firefox/WebKit
automatically. You always need the explicit `playwright install` (or
`playwright install --with-deps chromium` for a specific browser) as a
separate step. This framework's Dockerfile and every CI workflow include
this explicitly — if you're hitting this error, check whether a *new*
workflow you're adding forgot that step, or whether the Docker image cache
went stale after a Playwright version bump (browsers are versioned to match
the exact `playwright` package version).

---

## "Visual test fails on every single run, even with no UI changes"

**Cause:** Almost always font-rendering or anti-aliasing differences between
the machine that generated the baseline and the machine running the
comparison (e.g., baseline generated on macOS, CI runs on Ubuntu). Two
fixes: (1) always generate baselines from the *same environment* that will
run comparisons — i.e., generate them in CI/Docker, not on your laptop; (2)
loosen `max_diff_ratio` slightly (0.01 to 0.02) if the diffs are genuinely
sub-pixel noise, but verify that with the diff image first — don't loosen
the threshold blind.

---

## "API test fails with a schema validation error but the API 'looks fine'
in Postman"

**Cause:** Usually the schema itself is stale — the backend team shipped a
field rename/addition and the checked-in JSON schema wasn't updated. This
is a *good* failure (the framework caught real drift) even though it feels
like a false alarm. Resist the urge to just relax the schema to
`additionalProperties: true` everywhere — that defeats the purpose. Update
the schema deliberately, and if it happens often, consider generating
schemas from the API's OpenAPI spec automatically rather than hand-
maintaining them.
