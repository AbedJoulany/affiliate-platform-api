import re

import pytest

from app.main import app

DUMMY_UUID = "00000000-0000-0000-0000-000000000000"


def normalize_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", DUMMY_UUID, path)


def build_request_data(path: str, method: str) -> dict:
    if path.endswith("/login"):
        return {
            "data": {"username": "test@example.com", "password": "password"},
            "json": None,
        }

    if method in {"post", "put", "patch"}:
        return {"json": {}}

    return {}


def allowed_status_codes(method: str) -> set[int]:
    return {200, 201, 202, 204, 401, 403, 404, 422, 502, 503}


@pytest.mark.asyncio
async def test_all_openapi_endpoints(client):
    paths = app.openapi()["paths"]
    assert paths, "OpenAPI paths must be available"

    for raw_path, operations in paths.items():
        url = normalize_path(raw_path)
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue

            request_kwargs = build_request_data(raw_path, method)
            response = await client.request(method.upper(), url, **request_kwargs)

            assert response.status_code in allowed_status_codes(method), (
                f"Unexpected status for {method.upper()} {url}: "
                f"{response.status_code} - {response.text}"
            )
