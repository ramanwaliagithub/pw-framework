# Interview Questions — Architecture & Design Depth

Organized by theme. Each answer is written the way you'd actually say it out
loud — short, concrete, anchored to a real decision in this codebase, not a
textbook definition. Where relevant I've noted how to bridge to your
bw-pylonium/Basware experience.

---

## Architecture & Design Patterns

**Q: Walk me through why you chose a layered architecture instead of putting
everything in page objects.**

Because at 10k tests, a page object that also knows about config resolution,
retry logic, and logging becomes untestable and unreusable. Each layer has
exactly one reason to change: Core changes when the browser/config strategy
changes, Page Objects change when the UI changes, Service layer changes when
an API/DB contract changes. That's the Single Responsibility half of SOLID
applied at the module level, not just the class level. It's the same
instinct behind bw-pylonium — I didn't want every one of the 10+ engineers
using it to reimplement retry/wait logic per-framework.

**Q: Why Facade for PlaywrightManager instead of just using Playwright
directly in fixtures?**

Playwright's lifecycle is seven-plus ordered calls (start playwright, launch
browser, new context with N kwargs, start tracing, new page, and the
teardown mirror of all that). If that lives in conftest.py directly, every
new fixture variant (mobile viewport, authenticated session, multi-tab)
duplicates it. Facade means conftest.py just calls `.start()`/`.stop()` and
the class owns getting the sequence right exactly once.

**Q: Why is ConfigManager a Singleton but PlaywrightManager isn't?**

Config is read-only, environment-scoped, and identical for every test in a
run — there's no reason to reparse YAML 10,000 times. Browser state is the
opposite: it must be *unique per test* for isolation. Making PlaywrightManager
a singleton would mean test B inherits test A's cookies/localStorage/network
state — a correctness bug, not just a performance question. Singleton is a
tool for shared immutable-per-run state, not a default.

**Q: Explain the self-healing locator pattern — is this "AI-assisted"?**

No, and I'd correct an interviewer who conflated the two. It's deterministic:
try primary selector, on timeout try each fallback in order, log a WARNING
(not silent) when a fallback was needed. It protects against a class of
false-positive failures — a dev renaming a CSS class without breaking
functionality — while still surfacing the drift so it gets fixed, rather
than either (a) failing the build for a cosmetic change or (b) silently
masking it forever. True AI-assisted recovery (using vision models or DOM
embeddings to find a semantically-similar element when *all* selectors fail)
is a valid v2 direction but adds nondeterminism I wouldn't want as the
default path.

**Q: Strategy pattern shows up twice in this framework — auth and data
loaders. Why does that pattern recur?**

Both are "the caller doesn't want to know which concrete implementation
handles this, and new implementations get added over the project's life."
Auth: today it's Bearer, next environment might be OAuth2 client-credentials
— client code stays identical. Data loaders: today it's a JSON file, next
sprint the business team wants to maintain an Excel sheet instead — same
`load_test_data()` call site. Strategy is the pattern for "this varies, and
callers shouldn't have to branch on which variant."

---

## Pytest & Fixtures

**Q: Function-scoped vs session-scoped fixtures — how do you decide?**

Default to the narrowest scope that's correct (function-scoped), and widen
deliberately only when you've measured a real cost. In this framework,
`page` is function-scoped for test isolation — that's correct-by-default and
never in question. `app_config` is session-scoped because config really is
identical all run, and reparsing YAML per-test is pure waste with zero
isolation benefit. The mistake I see teams make is optimizing the browser
fixture to session-scope prematurely and then chasing flaky failures for
weeks because context state leaked across tests.

**Q: How do you know if a test failed, inside a fixture's teardown code?**

pytest's `request.node` doesn't have pass/fail info by default — you need
the `pytest_runtest_makereport` hook to stash it. I attach
`rep_setup`/`rep_call`/`rep_teardown` onto the test item via
`hookimpl(hookwrapper=True)`, then the `page` fixture teardown reads
`request.node.rep_call.failed` to decide whether to capture a screenshot/
trace. This is a genuinely non-obvious pytest internals question — most
people don't know this hook exists until they need conditional artifact
capture.

**Q: What's `--strict-markers` for and why do you always turn it on?**

Without it, a typo'd marker (`@pytest.mark.smok`) silently registers as a
new unknown marker instead of erroring — meaning that test quietly drops out
of every `-m smoke` CI run and nobody notices until a bug ships. With
`--strict-markers`, any marker not declared in `pytest.ini` fails collection
immediately. Cheap insurance against a very real failure mode at scale.

**Q: Retries — how do you avoid --reruns masking real flakiness/bugs?**

Two things: keep the rerun count low (1 for PR checks) so a genuinely
broken test still shows red within 2 attempts, and track rerun *frequency*
per test over time — if a test needs its rerun more than occasionally, that's
a signal to fix the root cause (usually a missing wait condition), not a
justification for bumping reruns to 3. Reruns are for transient
infrastructure noise, not a permanent patch over flaky test design.

---

## Playwright-Specific

**Q: Why did you build a custom Pillow-based visual diff instead of using
Playwright's built-in `to_have_screenshot()`?**

Because `to_have_screenshot()` is a Playwright *Test runner* feature (the JS/
TS `@playwright/test` framework) — it's not available on a plain `Page`
object from `sync_playwright()`, which is what a pytest-based Python
framework uses. I actually wrote it that way first, checked it against the
installed `PageAssertions` class, found the method wasn't there, and
rebuilt it with a portable Pillow diff instead. That's a real trap — the
JS and Python Playwright docs read as if the API surface is identical, and
for screenshot-diffing specifically, it isn't when you're outside the
Playwright Test runner.

**Q: How does context-per-test give you isolation, mechanically? What
would leak if you shared a context?**

A BrowserContext owns cookies, localStorage, sessionStorage, and permissions
state. Share a context across tests and test B inherits test A's login
session, cart contents, granted permissions (geolocation, notifications) —
tests stop being independent, and failures become order-dependent, which is
close to the worst debugging experience in test automation. New context per
test costs maybe 50-100ms; that's cheap insurance.

**Q: Storage-state reuse — doesn't that reintroduce the leakage problem
you just described?**

Storage state reuse is deliberately scoped: you save *one* known-good
login session (e.g., `standard_user.json`) and every test that opts in via
`--use-storage-state` starts from that identical baseline — it's shared
*starting state*, not shared *live state*. Each test still gets its own
context; they just don't each have to click through the login form. If a
test mutates that state (e.g., adds to cart) that mutation lives only in
that test's context and disappears when it closes — it never writes back to
the saved JSON file.

**Q: Tracing on every test vs only on failure — what's the tradeoff you
made?**

I start tracing on every test (`context.tracing.start()`) but only *save*
the trace file (`tracing.stop(path=...)`) on failure — otherwise
`tracing.stop()` with no path just discards it. The overhead of trace
*recording* is fairly low; the overhead of *writing* a trace.zip for every
one of 10,000 passing tests would be enormous disk/artifact-storage waste
for something nobody will ever open. You get full debuggability exactly
when you need it and zero storage cost when you don't.

---

## API & Database Layer

**Q: Why Playwright's APIRequestContext instead of `requests` for API
tests?**

Two reasons. First, shared tracing — if a test does an API call to seed
data and then verifies it in the UI, both show up in the same trace.zip,
which is a much better debugging artifact than correlating two separate
logs. Second, shared network configuration (proxy settings, TLS options)
between UI and API tests, so you're not maintaining two separate HTTP
client configs that can drift out of sync.

**Q: Explain your transaction/rollback pattern for DB test data — why not
just DELETE in a teardown fixture?**

A teardown-based DELETE only runs if the test framework actually reaches
teardown — if the process crashes, gets killed by a CI timeout, or the
teardown itself throws, orphaned data survives. Wrapping seed + assertions
in a single DB transaction with `finally: trans.rollback()` guarantees
cleanup at the *connection* level regardless of what happens up the stack.
I proved this really works, not just in theory — inserted a row inside the
transaction context, confirmed it was visible mid-transaction, then
confirmed it was gone after the `with` block exited.

**Q: How would you extend the DB layer to a new database vendor, say
Snowflake?**

One line in `_DRIVER_DIALECTS` mapping `"snowflake"` to its SQLAlchemy
dialect string (`snowflake://`), assuming the `snowflake-sqlalchemy` package
is installed. The `DBClient` class itself has zero vendor-specific code —
that's the point of building on SQLAlchemy's dialect abstraction rather than
writing a bespoke connector per database.

---

## Data & Test Design

**Q: Builder pattern for test data — why not just a factory function with
keyword arguments?**

A factory function with 8 keyword args either forces callers to pass all 8
every time, or you're relying on defaults and losing the "what does a valid
User actually look like" documentation value. Builder lets you write
`UserDataBuilder().with_zip_code("90210").build()` — the intent (I only care
about zip code for this test) is visible in the test itself, and adding a
9th field later doesn't break any existing call sites the way adding a
required positional arg would.

**Q: How do you decide between static test data files (JSON/YAML/CSV/Excel)
and dynamic Faker-generated data?**

Static files: when the *specific values* matter to the test — known bad
credentials, boundary values, data a business stakeholder needs to review
or edit without touching code. Dynamic Faker data: when only the *shape* of
the data matters and using the same email/username across parallel test runs
would cause collisions (e.g., "create a new user" tests running concurrently
under xdist against a shared environment) — random uniqueness is a feature
there, not a nice-to-have.

---

## CI/CD & Scale

**Q: Your PR workflow runs a 3-browser matrix on every PR — doesn't that
get expensive/slow at scale?**

It's deliberately scoped to `-m smoke` only, not the full regression suite —
smoke tests are a small, fast, high-signal subset by design. Full regression
(much larger, `--reruns 2`) is nightly, not per-PR. That split is the actual
answer to "how do you keep CI fast without losing coverage": run a small
trusted subset synchronously on every change, run the expensive full sweep
asynchronously on a schedule, and gate releases on the asynchronous run
having passed recently.

**Q: How would you scale this to support the "10,000 tests, multiple teams"
requirement from a real Fortune 500 ask?**

See docs/scaling_strategy.md for the full breakdown, but the headline
points: (1) shard the suite across many parallel CI runners, not just xdist
workers within one runner — xdist parallelizes within a machine, sharding
parallelizes across machines; (2) move from function-scoped browser+context
to session-scoped browser / function-scoped context once you've confirmed
context reset is actually clean, since browser launch is the expensive part;
(3) split page objects and fixtures into a separately-versioned internal
package (exactly what bw-pylonium was) so 4+ teams consume it via Artifactory
rather than each maintaining a fork.

---

## Behavioral / Leadership (bridge to your experience)

**Q: Tell me about a time you built something that other teams adopted.**

This is your bw-pylonium story — sole architect, published to private
Artifactory, adopted by 10+ engineers across 4+ frameworks at Basware. The
narrative arc that lands well: what pain existed before it (duplicated
retry/wait logic per team), the design decision that made adoption easy
(the wrapper API, not a rewrite of what teams already used), and how you
measured success (adoption count, not just "I built it").

**Q: How do you handle a flaky test in a large shared suite?**

Don't immediately reach for `--reruns`. Reproduce locally first, check
whether it's a genuine race condition (missing wait) vs environment noise
(shared test DB, rate limiting) vs true nondeterminism in the app. Fix at
the root when it's a wait/synchronization issue — that's most of them. Only
lean on rerun tolerance for genuinely external flakiness you don't control
(a third-party API's own occasional 503s, for instance).
