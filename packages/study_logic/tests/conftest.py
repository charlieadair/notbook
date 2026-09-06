from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from study_logic.api import install_study_logic
from study_logic.vault import InMemoryVault, create_fixture_vault


@pytest.fixture
def fixture_vault() -> InMemoryVault:
    return create_fixture_vault()


@pytest.fixture
def client(fixture_vault: InMemoryVault) -> TestClient:
    app = FastAPI()
    install_study_logic(app, retrieve=fixture_vault.retrieve)
    return TestClient(app)


@pytest.fixture
def empty_client() -> TestClient:
    app = FastAPI()
    install_study_logic(app, retrieve=InMemoryVault().retrieve)
    return TestClient(app)
