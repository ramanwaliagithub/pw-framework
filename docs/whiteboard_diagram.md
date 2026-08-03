# Framework Architecture — Interview Whiteboard Version

## Simple Layer Diagram (draw this top to bottom)

```mermaid
graph TD
    Tests["🧪 TESTS<br/>tests/ui/, tests/api/<br/>(smoke, regression, a11y, visual)"]
    
    Fixtures["🔌 FIXTURES<br/>conftest.py<br/>(wires everything together)"]
    
    Pages["📄 PAGE OBJECTS<br/>src/pages/<br/>BasePage + LoginPage, InventoryPage..."]
    
    Core["⚙️ CORE<br/>src/core/<br/>ConfigManager (Singleton)<br/>PlaywrightManager (Facade)<br/>BrowserFactory (Factory)"]
    
    Services["🔗 SERVICES<br/>src/api/ + src/db/<br/>APIClient + DBClient"]
    
    Utils["🛠️ UTILITIES<br/>src/utils/<br/>accessibility, visual, mocking, performance"]

    Tests --> Fixtures
    Fixtures --> Core
    Fixtures --> Services
    Pages --> Core
    Tests --> Pages
    Tests -.optional.-> Utils
    Pages -.optional.-> Utils

    style Tests fill:#e8f4f8
    style Fixtures fill:#fff4e0
    style Core fill:#e0f0e8
    style Services fill:#f0e8f8
    style Pages fill:#e0f0e8
    style Utils fill:#f8f0e0
```

**How to talk through it, top to bottom:**
"Tests sit at the top and don't know anything about Playwright internals — they just ask pytest for a `page` fixture. That fixture (in conftest.py) is the wiring layer — it goes to Core to actually spin up a browser. Page Objects also depend on Core (they need a `page` object to click things), but Tests only ever talk to Page Objects, never touch Core directly. Services (API/DB) are separate from UI entirely, so an API test never needs a browser at all."

---

## Pattern Cheat-Sheet (say this from memory)

```mermaid
graph LR
    subgraph "1 instance for whole run"
        A[ConfigManager<br/>SINGLETON]
    end
    
    subgraph "1 instance PER TEST"
        B[PlaywrightManager<br/>FACADE]
        C[new BrowserContext]
    end
    
    subgraph "picks the right one"
        D[BrowserFactory<br/>FACTORY]
        E[AuthStrategy<br/>STRATEGY]
        F[Data Loaders<br/>STRATEGY]
    end

    A -.read by.-> B
    D --> B
    B --> C

    style A fill:#ffd166
    style B fill:#06d6a0
    style D fill:#118ab2
    style E fill:#118ab2
    style F fill:#118ab2
```

**One-liner per pattern (say these fast, in order):**
1. **Singleton** = "one shared thing" → Config
2. **Facade** = "one button hides many steps" → PlaywrightManager.start()/stop()
3. **Factory** = "give me the right browser, I don't care how" → BrowserFactory
4. **Strategy** = "swap the implementation without changing the caller" → Auth, Data loaders
5. **Template Method + Fluent** = "shared skeleton, chainable calls" → BasePage
6. **Builder** = "construct step by step, override only what you need" → UserDataBuilder
7. **Repository** = "hide the database, expose query()/execute()" → DBClient
