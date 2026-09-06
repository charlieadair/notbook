from app.inference.stub import STUB_COMPLETE, StubInference


def test_stub_embed_and_complete_callable():
    adapter = StubInference()
    vectors = adapter.embed(["eigenvalues", "eigenvalues", "unrelated token soup"])
    assert len(vectors) == 3
    assert len(vectors[0]) == 64
    assert vectors[0] == vectors[1]
    assert vectors[0] != vectors[2]
    assert adapter.complete([{"role": "user", "content": "hello"}]) == STUB_COMPLETE


def test_inference_endpoint_reports_stub(client):
    response = client.get("/inference")
    assert response.status_code == 200
    body = response.json()
    assert body["adapter"] == "stub"
    assert body["study_logic_mounted"] is False
    assert "api_key" not in body
    assert "OPENAI" not in str(body)
