def test_dashboard_only_flags_dependency_correct_risks(client):
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    risks = [order["code"] for order in data["orders"] if order["affected"]]
    assert risks == ["ORD-4821", "ORD-4824"]
    assert next(o for o in data["orders"] if o["code"] == "ORD-4830")["shortage"] == 0
    assert "ORD-4799" not in [order["code"] for order in data["orders"]]


def test_options_include_on_time_late_and_infeasible(client):
    detail = client.get("/api/orders/1").json()
    statuses = {option["status"] for option in detail["options"]}
    assert statuses == {"on_time", "late", "infeasible"}
    assert detail["shortage"] == 40
    assert detail["projected_date"] == "2026-10-10"


def test_proposal_has_no_side_effect_then_approval_is_idempotent(client):
    before = client.get("/api/orders/1").json()
    option = next(o for o in before["options"] if o["type"] == "transfer" and o["status"] == "on_time")
    proposal = client.post("/api/proposals", json={
        "order_id": 1, "option_type": option["type"], "source_ref": option["source_ref"],
        "quantity": 40, "expected_arrival": option["expected_arrival"],
        "actor": "Maya Chen", "rationale": "Fastest on-time recovery with confirmed stock.",
    })
    assert proposal.status_code == 201
    assert proposal.json()["inventory_changed"] is False
    unchanged = client.get("/api/orders/1").json()
    assert unchanged["shortage"] == 40

    proposal_id = proposal.json()["id"]
    approval = client.post(f"/api/proposals/{proposal_id}/approve", json={"actor": "Maya Chen", "idempotency_key": "approval-test-0001"})
    assert approval.status_code == 200
    assert approval.json()["order_outlook"]["shortage"] == 0
    replay = client.post(f"/api/proposals/{proposal_id}/approve", json={"actor": "Maya Chen", "idempotency_key": "approval-test-0001"})
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert any(e["action"] == "inventory.reserved" for e in client.get("/api/audit").json())


def test_explanation_cites_supporting_records(client):
    answer = client.post("/api/orders/1/explain").json()
    assert "40" in answer["answer"]
    assert {link["label"] for link in answer["links"]} >= {"ORD-4821", "AX-440", "INB-7392"}



def _propose(client, order_id, option, quantity):
    return client.post("/api/proposals", json={
        "order_id": order_id, "option_type": option["type"], "source_ref": option["source_ref"],
        "quantity": quantity, "expected_arrival": option["expected_arrival"],
        "actor": "Maya Chen", "rationale": "Competing use of the same transfer stock.",
    })


def test_infeasible_option_cannot_be_proposed(client):
    detail = client.get("/api/orders/1").json()
    infeasible = next(o for o in detail["options"] if o["status"] == "infeasible")
    assert _propose(client, 1, infeasible, 40).status_code == 422


def test_competing_proposal_goes_stale_without_inventory_effects(client):
    transfer = next(o for o in client.get("/api/orders/1").json()["options"] if o["type"] == "transfer")
    first = _propose(client, 1, transfer, 40).json()["id"]
    second = _propose(client, 2, transfer, 25).json()["id"]
    assert client.post(f"/api/proposals/{first}/approve", json={"actor": "Maya Chen", "idempotency_key": "approval-first-01"}).status_code == 200

    stale = client.post(f"/api/proposals/{second}/approve", json={"actor": "Maya Chen", "idempotency_key": "approval-second-01"})
    assert stale.status_code == 409
    assert client.get("/api/orders/2").json()["shortage"] == 25
    assert any(e["action"] == "approval.rejected_stale" for e in client.get("/api/audit").json())
    reused = client.post(f"/api/proposals/{second}/approve", json={"actor": "Maya Chen", "idempotency_key": "approval-first-01"})
    assert reused.status_code == 409
