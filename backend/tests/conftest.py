from collections.abc import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.noaa import get_noaa_client


@pytest.fixture
def client_factory():
    def make_client(handler: Callable[[httpx.Request], httpx.Response]) -> TestClient:
        async def override_noaa_client():
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                yield client

        app.dependency_overrides[get_noaa_client] = override_noaa_client
        return TestClient(app)

    yield make_client
    app.dependency_overrides.clear()