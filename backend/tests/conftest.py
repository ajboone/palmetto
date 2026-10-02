from collections.abc import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import NWS_USER_AGENT
from app.main import app
from app.services.charleston_gis import get_gis_client
from app.services.noaa import get_noaa_client
from app.services.weather import get_weather_client


@pytest.fixture
def client_factory():
    def make_client(handler: Callable[[httpx.Request], httpx.Response]) -> TestClient:
        def override(headers: dict[str, str] | None = None):
            async def dependency():
                async with httpx.AsyncClient(
                    transport=httpx.MockTransport(handler), headers=headers
                ) as client:
                    yield client

            return dependency

        app.dependency_overrides[get_noaa_client] = override()
        app.dependency_overrides[get_weather_client] = override(
            {"User-Agent": NWS_USER_AGENT, "Accept": "application/geo+json"}
        )
        app.dependency_overrides[get_gis_client] = override()
        return TestClient(app)

    yield make_client
    app.dependency_overrides.clear()