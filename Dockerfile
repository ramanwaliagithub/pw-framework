# Playwright's official image ships matching browser binaries + OS deps
# pre-installed, avoiding the classic "works on my machine, fails in CI"
# headless-browser dependency drift problem.
FROM mcr.microsoft.com/playwright/python:v1.56.0-jammy

WORKDIR /app

# Install uv via the official static binary (no pip bootstrap needed) —
# pinned to a specific version for reproducible builds, per Astral's own
# guidance (see docs.astral.sh/uv/guides/integration/docker).
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /usr/local/bin/

# Install deps first (separate layer) so `docker build` cache is only
# invalidated by dependency changes, not every source-code edit — this
# matters a lot when CI rebuilds this image dozens of times a day.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

# Re-run browser install explicitly: the base image has browsers, but not
# necessarily the exact versions the pinned `playwright` package expects
# after `uv sync` resolves its own version.
RUN uv run playwright install --with-deps chromium firefox webkit

ENV PYTHONUNBUFFERED=1 \
    TEST_ENV=qa \
    HEADLESS=true \
    PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["uv", "run", "pytest"]
CMD ["-m", "smoke"]
