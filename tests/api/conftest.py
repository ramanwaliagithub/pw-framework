from __future__ import annotations

from typing import Generator

import pytest
from playwright.sync_api import sync_playwright

from src.api.api_client import APIClient


@pytest.fixture(scope="session")
def api_client(app_config) -> Generator[APIClient, None, None]:
    with sync_playwright() as pw:
        client = APIClient(pw, base_url=app_config.api_base_url)
        yield client
        client.dispose()
