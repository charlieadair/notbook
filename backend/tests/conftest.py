from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def app(data_dir: Path):
    settings = Settings(
        data_dir=data_dir,
        inference_adapter="stub",
        openai_api_base=None,
        openai_api_key=None,
    )
    return create_app(settings)


@pytest.fixture
def client(app) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def notebook_id(client: TestClient) -> str:
    response = client.post("/api/v1/notebooks", json={"title": "Linear Algebra"})
    assert response.status_code == 201, response.text
    return response.json()["id"]
