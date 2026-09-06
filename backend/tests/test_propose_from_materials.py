def test_propose_empty_notebook_returns_no_topics(client, notebook_id):
    proposed = client.post(f"/api/v1/notebooks/{notebook_id}/topics/propose")
    assert proposed.status_code == 200
    assert proposed.json() == []


def test_propose_from_ingested_chunks(client, notebook_id):
    pasted = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        json={
            "filename": "cell-cycle.md",
            "text": (
                "# Mitosis\n"
                "Mitosis is a type of cell division that produces two identical daughter cells.\n"
            ),
        },
    )
    assert pasted.status_code == 201, pasted.text

    proposed = client.post(f"/api/v1/notebooks/{notebook_id}/topics/propose")
    assert proposed.status_code == 200, proposed.text
    names = [row["name"] for row in proposed.json()]
    assert "Mitosis" in names
    assert all(row["confirmed"] is False for row in proposed.json())
