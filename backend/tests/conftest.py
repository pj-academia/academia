from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from app.bootstrap import Container
from app.main import create_app
from app.shared.config import Settings


class FakeCheck:
    def __init__(self, name: str, healthy: bool) -> None:
        self.name = name
        self.healthy = healthy

    async def is_healthy(self) -> bool:
        return self.healthy


def fake_container(
    *checks: FakeCheck,
) -> Callable[[Settings], AbstractAsyncContextManager[Container]]:
    @asynccontextmanager
    async def factory(_: Settings) -> AsyncIterator[Container]:
        yield Container(health_checks=list(checks))

    return factory


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def make_client(settings: Settings) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def build(*checks: FakeCheck) -> TestClient:
        client = TestClient(create_app(settings, container_factory=fake_container(*checks)))
        client.__enter__()
        clients.append(client)
        return client

    yield build
    for client in clients:
        client.__exit__(None, None, None)
