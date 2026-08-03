# Architecture & Sequence Diagrams

## 1. Layered Architecture

```mermaid
graph TB
    subgraph "Test Layer"
        T1[Smoke Tests]
        T2[Regression Tests]
        T3[API Tests]
        T4[Accessibility Tests]
        T5[Visual Tests]
    end

    subgraph "Fixture / Wiring Layer"
        F1[conftest.py]
        F2["page fixture"]
        F3["api_client fixture"]
        F4["app_config fixture"]
    end

    subgraph "Page Object Layer"
        P1[BasePage]
        P2[LoginPage / InventoryPage / ...]
        P3["Reusable Components<br/>(SortDropdown, CartBadge)"]
    end

    subgraph "Core Layer"
        C1[PlaywrightManager]
        C2[BrowserFactory]
        C3[ConfigManager]
        C4[Logger]
    end

    subgraph "Service Layer"
        S1[APIClient]
        S2[DBClient]
        S3[AuthStrategy]
    end

    subgraph "Utility Layer"
        U1[Data Loaders / Builders]
        U2[Accessibility Checker]
        U3[Visual Testing]
        U4[Network Mocking]
        U5[Performance Metrics]
        U6[PDF Validation]
    end

    subgraph "External"
        E1[(Browser)]
        E2[(REST API)]
        E3[(Database)]
    end

    T1 & T2 & T4 & T5 --> F2
    T3 --> F3
    F2 --> C1
    F3 --> S1
    F4 --> C3

    P2 --> P1
    P2 --> P3
    P1 --> E1

    C1 --> C2
    C1 --> C3
    C1 --> C4
    C2 --> E1

    S1 --> S3
    S1 --> E2
    S2 --> E3

    P1 -.uses.-> U2
    P1 -.uses.-> U3
    P1 -.uses.-> U4
    P1 -.uses.-> U5
    T2 -.uses.-> U1
    T2 -.uses.-> U6

    style C1 fill:#4a90d9
    style C3 fill:#4a90d9
    style P1 fill:#5cb85c
    style S1 fill:#f0ad4e
    style S2 fill:#f0ad4e
```

**Reading this diagram in an interview:** point at the dependency direction — tests depend on fixtures, fixtures depend on core/service layers, page objects depend only on BasePage + Playwright's Page object. Nothing in Core or Service layers imports anything from Test or Page Object layers. That one-directional dependency flow is *the* answer to "how did you keep this maintainable at scale" — you can change a page object without touching PlaywrightManager, and vice versa.

---

## 2. Test Execution Sequence (UI test, happy path)

```mermaid
sequenceDiagram
    participant CI as GitHub Actions
    participant Pytest as pytest + xdist
    participant Fixture as page fixture (conftest.py)
    participant PWM as PlaywrightManager
    participant BF as BrowserFactory
    participant PO as LoginPage (Page Object)
    participant Browser as Real Browser

    CI->>Pytest: pytest -m smoke -n auto
    Pytest->>Fixture: request "page" fixture
    Fixture->>Fixture: new_correlation_id()
    Fixture->>PWM: PlaywrightManager(config).start()
    PWM->>BF: BrowserFactory.create(playwright, config)
    BF->>Browser: chromium.launch(headless=True)
    Browser-->>BF: Browser instance
    BF-->>PWM: Browser instance
    PWM->>Browser: new_context() + tracing.start()
    PWM->>Browser: new_page()
    Browser-->>PWM: Page
    PWM-->>Fixture: Page (yielded to test)
    Fixture-->>Pytest: page object injected

    Pytest->>PO: LoginPage(page).open()
    PO->>Browser: page.goto(url)
    Pytest->>PO: login.login(user, pass)
    PO->>Browser: resilient_locator().fill()
    PO->>Browser: resilient_locator().click()
    Browser-->>PO: DOM updated

    Pytest->>Pytest: assert inventory.is_loaded()

    alt Test Passed
        Pytest->>PWM: manager.stop(test_failed=False, ...)
        PWM->>Browser: tracing.stop() [discarded]
    else Test Failed
        Pytest->>PWM: manager.stop(test_failed=True, ...)
        PWM->>Browser: screenshot() + tracing.stop(save)
        PWM-->>Pytest: artifact paths
        Pytest->>Pytest: attach to Allure report
    end

    PWM->>Browser: context.close() + browser.close()
    Pytest-->>CI: JUnit XML + Allure results + HTML report
```

---

## 3. Self-Healing Locator Flow

```mermaid
flowchart TD
    A[BasePage.click / fill called] --> B{Try primary selector}
    B -->|Found within 2s| C[Use primary locator]
    B -->|Timeout| D{Fallback selectors remain?}
    D -->|Yes| E[Try next fallback selector]
    E --> F{Found within 2s?}
    F -->|Yes| G[Log WARNING: healed via fallback]
    F -->|No| D
    D -->|No| H[Raise ElementNotFoundError]
    C --> I[Perform action: click/fill/read text]
    G --> I
    H --> J[Test fails with clear diagnostic]

    style H fill:#d9534f
    style G fill:#f0ad4e
    style C fill:#5cb85c
```

---

## 4. CI/CD Deployment Pipeline

```mermaid
flowchart LR
    A[Developer commits] --> B[Push to feature branch]
    B --> C[Open Pull Request]
    C --> D[PR Validation Workflow]

    D --> D1[Lint: Black/isort/Ruff]
    D --> D2[Type check: mypy]
    D1 & D2 --> D3[Smoke tests<br/>3-browser matrix]
    D3 --> D4[API tests]
    D4 --> E{All checks green?}

    E -->|No| F[Slack notify: PR failed]
    F --> B

    E -->|Yes| G[Human code review]
    G --> H[Merge to main]

    H --> I[Nightly Regression<br/>3 browsers x 2 Python versions]
    I --> J[Publish Allure report to GitHub Pages]
    J --> K{Regression green?}
    K -->|No| L[Teams alert]

    H -.tag release.-> M[Release Pipeline]
    M --> N[Full suite: smoke+regression+api]
    N --> O{Pass?}
    O -->|Yes| P[Tag GitHub Release]
    O -->|No| Q[Block release, notify]
    P --> R[Production Deployment]
    R --> S[Scheduled Smoke<br/>every 2h prod sanity]

    style E fill:#f0ad4e
    style O fill:#f0ad4e
    style P fill:#5cb85c
    style F fill:#d9534f
    style Q fill:#d9534f
```

---

## 5. Database Transaction Isolation Pattern

```mermaid
sequenceDiagram
    participant Test
    participant DBClient
    participant Conn as SQLAlchemy Connection
    participant DB as Database

    Test->>DBClient: with db.transaction() as tx:
    DBClient->>Conn: engine.connect()
    DBClient->>Conn: conn.begin()
    Conn->>DB: BEGIN

    Test->>DBClient: tx.execute(INSERT seed data)
    DBClient->>DB: INSERT (uncommitted)

    Test->>Test: run UI/API assertions<br/>against seeded data

    alt Assertion passes
        Test->>DBClient: exit "with" block normally
    else Assertion raises
        Test->>DBClient: exception propagates
    end

    DBClient->>Conn: trans.rollback() [always runs - finally block]
    Conn->>DB: ROLLBACK
    DBClient->>Conn: conn.close()

    Note over DB: Seeded data never persisted.<br/>Next test starts from clean state<br/>regardless of pass/fail.
```
