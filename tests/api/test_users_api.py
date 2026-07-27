"""
API tests against reqres.in (public demo API) — demonstrates the API
layer end-to-end: GET, POST, schema validation, fluent assertions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "data" / "json" / "user_schema.json"


@pytest.fixture(scope="module")
def user_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text())


@pytest.mark.api
@pytest.mark.smoke
def test_get_single_user_returns_valid_schema(api_client, user_schema):
    response = api_client.get("/users/2")
    response.expect_status(200).validate_schema(user_schema)
    assert response.json()["data"]["id"] == 2


@pytest.mark.api
@pytest.mark.regression
def test_create_user_returns_201(api_client):
    payload = {"name": "Raman Walia", "job": "Senior SDET"}
    response = api_client.post("/users", data=payload)
    response.expect_status(201)
    body = response.json()
    assert body["name"] == payload["name"]
    assert body["job"] == payload["job"]
    assert "id" in body


@pytest.mark.api
@pytest.mark.regression
def test_get_nonexistent_user_returns_404(api_client):
    response = api_client.get("/users/9999")
    response.expect_status(404)
