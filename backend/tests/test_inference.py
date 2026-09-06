import httpx

from app.inference.openai_compatible import OpenAICompatibleInference
from app.inference.stub import STUB_COMPLETE, StubInference


def test_stub_embed_and_complete_callable():
    adapter = StubInference()
    vectors = adapter.embed(["eigenvalues", "eigenvalues", "unrelated token soup"])
    assert len(vectors) == 3
    assert len(vectors[0]) == 64
    assert vectors[0] == vectors[1]
    assert vectors[0] != vectors[2]
    assert adapter.complete([{"role": "user", "content": "hello"}]) == STUB_COMPLETE


def test_openai_compatible_sets_connect_and_read_timeouts():
    adapter = OpenAICompatibleInference(
        api_base="https://openrouter.ai/api/v1",
        api_key="sk-test",
        embed_model="nvidia/nemotron-3-embed-1b:free",
        chat_model="unused",
        connect_timeout=1.5,
        read_timeout=2.5,
    )
    timeout = adapter._client.timeout
    assert timeout.connect == 1.5
    assert timeout.read == 2.5
    assert timeout.write == 2.5
    assert timeout.pool == 1.5


def test_openai_compatible_legacy_timeout_applies_to_all():
    adapter = OpenAICompatibleInference(
        api_base="http://127.0.0.1:9/v1",
        api_key="sk-test",
        embed_model="m",
        chat_model="c",
        timeout=7.0,
    )
    timeout = adapter._client.timeout
    assert timeout.connect == 7.0
    assert timeout.read == 7.0


def test_openai_embed_propagates_read_timeout(monkeypatch):
    adapter = OpenAICompatibleInference(
        api_base="https://example.invalid/v1",
        api_key="sk-test",
        embed_model="m",
        chat_model="c",
        connect_timeout=0.2,
        read_timeout=0.2,
    )

    def boom(*_args, **_kwargs):
        raise httpx.ReadTimeout("stalled")

    monkeypatch.setattr(adapter._client, "post", boom)
    try:
        adapter.embed(["spectral theorem"])
    except httpx.ReadTimeout:
        pass
    else:
        raise AssertionError("embed must surface HTTP read timeout")


def test_inference_endpoint_reports_stub(client):
    response = client.get("/inference")
    assert response.status_code == 200
    body = response.json()
    assert body["adapter"] == "stub"
    assert body["study_logic_mounted"] is True
    assert "api_key" not in body
    assert "OPENAI" not in str(body)
