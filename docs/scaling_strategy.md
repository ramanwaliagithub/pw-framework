# Scaling Strategy — From This Framework to 10,000+ Tests / Multiple Teams

This document is the honest answer to "how would this actually get to
Fortune-500 scale" — what's already handled by the current design, and what
would need to change and why.

---

## What's already scale-ready (no changes needed)

- **Layered architecture** — teams can own different page-object packages
  (checkout team owns `pages/checkout/`, admin team owns `pages/admin/`)
  without touching Core/Service layers.
- **Config resolution** (env var > .env > YAML) — supports N environments
  without code changes, just new YAML blocks.
- **xdist parallelization** — already wired via `-n auto`, scales with
  runner core count.
- **DB transaction isolation** — safe under high parallelism since each
  test's DB work is isolated to its own connection/transaction.

## What needs to change, in priority order

### 1. Test sharding across multiple CI runners (not just xdist)

xdist parallelizes *within one machine*. At 10,000 tests, even a 32-core
self-hosted runner will take too long serialized through one job. The real
fix is **sharding**: split the suite into N groups (by test file hash, by
historical duration, or by team ownership) and run each group as a
*separate parallel CI job*, each internally still using xdist.

```yaml
strategy:
  matrix:
    shard: [1, 2, 3, 4, 5, 6, 7, 8]
steps:
  - run: pytest --shard-id=${{ matrix.shard }} --num-shards=8 -n auto
```

Duration-based sharding (via `pytest-split` or a custom `.test_durations`
file) beats naive alphabetical sharding — otherwise one shard with all the
slow UI tests bottlenecks the whole run while 7 others finish in 2 minutes.

### 2. Browser reuse strategy

Currently: new Browser + new Context per test (safest default, documented
in Chapter 2). At scale, browser *launch* (not context creation) is the
expensive part — roughly 300-800ms depending on browser/machine. Moving to
**session-scoped Browser + function-scoped Context** cuts that cost to
near-zero per test while preserving isolation, since Context (not Browser)
is what owns cookies/storage/permissions state:

```python
@pytest.fixture(scope="session")
def browser(app_config):
    with sync_playwright() as pw:
        b = BrowserFactory.create(pw, app_config)
        yield b
        b.close()

@pytest.fixture(scope="function")
def page(browser, app_config):
    context = browser.new_context(...)
    yield context.new_page()
    context.close()
```

This is a real tradeoff, not a free upgrade — it means a single corrupted
browser process (rare, but happens) can take down every test using it for
that xdist worker's lifetime. Worth the risk at scale; worth documenting
the risk explicitly so the next engineer understands why it changed.

### 3. Internal package extraction (the bw-pylonium pattern, generalized)

At 4+ teams, forking this repo per team guarantees drift. The Core +
Service + Utility layers (everything except Page Objects and Tests) should
be extracted into a versioned internal package published to an artifact
registry (Artifactory/Nexus/private PyPI) — exactly the model that made
bw-pylonium work at Basware. Teams pin a version
(`pw-framework-core==2.3.1` in their `pyproject.toml`), upgrade
deliberately, and file issues against a central repo instead of
hand-patching their fork.

### 4. Test data isolation at higher parallelism

DB transaction rollback (Chapter 3) handles isolation per-test. At high
parallelism against a *shared* environment (not per-test ephemeral DBs),
watch for:
- **Unique constraint collisions** — two parallel tests both trying to
  create a user with the same email. Faker-based dynamic data (Chapter 4)
  already mitigates this; audit for any remaining hardcoded test emails.
- **Read-modify-write races on shared fixtures** — e.g., two tests both
  editing "the first employee in the list." Prefer creating your own
  scoped test data over mutating shared seed data.

### 5. Flaky-test quarantine process

At 10,000 tests, some nonzero percentage will be flaky no matter how
careful the framework is. Don't let flaky tests block every PR for every
team. Practical process: a test that fails its rerun threshold (Chapter 5)
gets auto-tagged `@pytest.mark.quarantine` via a scheduled job that parses
CI history, is excluded from the blocking PR-validation run, but still
executes in nightly regression with a dashboard tracking quarantine count
over time — visibility without blocking velocity, with an explicit
expectation that quarantine is temporary, not a permanent escape hatch.

### 6. Selective test execution (impact analysis)

At full scale, running all 10,000 tests on every PR is wasteful even
sharded. A more mature setup maps changed files to affected test modules
(e.g., via import-graph analysis or a maintained ownership manifest) and
runs only the affected subset on PRs, with the full suite still running
nightly as a safety net. This is a meaningfully harder engineering
investment — worth naming as "the next thing I'd build" in an interview
rather than pretending it's trivial.

---

## What I would explicitly NOT do

- **Wouldn't** make BrowserFactory or PlaywrightManager singletons to "save
  resources" — the isolation cost of getting that wrong is much higher than
  the resource savings, and the real fix (session-scoped browser, above)
  gets most of the benefit without that risk.
- **Wouldn't** relax API schema validation to reduce false-positive
  failures — the fix for schema drift is process (update the schema when
  the API changes), not weaker assertions.
- **Wouldn't** increase global rerun counts to hide flakiness at scale —
  that trades visible pain now for invisible, compounding pain later as the
  suite's signal quality degrades team by team.
