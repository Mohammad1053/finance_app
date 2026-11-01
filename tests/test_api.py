import pytest


def make_transaction(client, seed, **overrides):
    """Create a transaction through the API with sensible defaults."""
    payload = {
        "amount": 350000,
        "date": "2026-10-25",
        "description": "خرید هفتگی",
        "payment_method_id": seed.cash_id,
        "category_id": seed.food_id,
    }
    payload.update(overrides)
    return client.post("/transactions/", json=payload)


# ---------- Payment methods ----------
def test_payment_method_crud_and_duplicate(client):
    res = client.post("/payment-methods/", json={"name": "چک"})
    assert res.status_code == 201
    pm_id = res.json()["id"]

    assert client.post("/payment-methods/",
                       json={"name": "چک"}).status_code == 409

    res = client.put(f"/payment-methods/{pm_id}", json={"name": "چک بانکی"})
    assert res.json()["name"] == "چک بانکی"

    assert client.delete(f"/payment-methods/{pm_id}").status_code == 204
    assert client.put(
        f"/payment-methods/{pm_id}", json={"name": "x"}).status_code == 404


def test_empty_payment_method_name_is_rejected(client):
    assert client.post("/payment-methods/",
                       json={"name": ""}).status_code == 422


# ---------- Categories ----------
def test_category_create_duplicate_and_invalid_type(client):
    assert client.post(
        "/categories/", json={"name": "اجاره", "type": "expense"}).status_code == 201
    assert client.post(
        "/categories/", json={"name": "اجاره", "type": "expense"}).status_code == 409
    assert client.post(
        "/categories/", json={"name": "x", "type": "other"}).status_code == 422


def test_category_list_filtered_by_type(client, seed):
    res = client.get("/categories/", params={"type": "income"})
    assert [c["name"] for c in res.json()] == ["حقوق"]


# ---------- Transactions ----------
def test_create_and_read_transaction(client, seed):
    res = make_transaction(client, seed)
    assert res.status_code == 201
    body = res.json()
    assert body["amount"] == 350000
    assert body["category"]["name"] == "خوراک"
    assert body["payment_method"]["name"] == "نقد"

    assert client.get(f"/transactions/{body['id']}").status_code == 200


@pytest.mark.parametrize("amount", [0, -500])
def test_non_positive_amount_is_rejected(client, seed, amount):
    assert make_transaction(client, seed, amount=amount).status_code == 422


def test_unknown_references_give_404(client, seed):
    assert make_transaction(client, seed, category_id=999).status_code == 404
    assert make_transaction(
        client, seed, payment_method_id=999).status_code == 404


def test_patch_changes_only_given_fields(client, seed):
    tx_id = make_transaction(client, seed).json()["id"]
    res = client.patch(f"/transactions/{tx_id}", json={"amount": 400000})
    assert res.status_code == 200
    assert res.json()["amount"] == 400000
    assert res.json()["description"] == "خرید هفتگی"


def test_delete_transaction(client, seed):
    tx_id = make_transaction(client, seed).json()["id"]
    assert client.delete(f"/transactions/{tx_id}").status_code == 204
    assert client.get(f"/transactions/{tx_id}").status_code == 404
    assert client.delete(f"/transactions/{tx_id}").status_code == 404


def test_used_category_and_payment_method_cannot_be_deleted(client, seed):
    make_transaction(client, seed)
    assert client.delete(f"/categories/{seed.food_id}").status_code == 409
    assert client.delete(f"/payment-methods/{seed.cash_id}").status_code == 409
    # Unused ones can be deleted
    assert client.delete(f"/payment-methods/{seed.card_id}").status_code == 204


def test_filters(client, seed):
    make_transaction(client, seed, amount=350000,
                     date="2026-10-25", description="خرید هفتگی")
    make_transaction(
        client, seed, amount=20_000_000, date="2026-10-26",
        description="حقوق ماه", category_id=seed.salary_id,
    )
    make_transaction(client, seed, amount=95000,
                     date="2026-11-02", description="نان")

    def count(**params):
        return len(client.get("/transactions/", params=params).json())

    assert count() == 3
    assert count(min_amount=300000) == 2
    assert count(max_amount=100000) == 1
    assert count(search="نان") == 1
    assert count(category_id=seed.food_id) == 2
    assert count(date_from="2026-10-26", date_to="2026-10-31") == 1
    assert count(min_amount=300000, category_id=seed.food_id) == 1
