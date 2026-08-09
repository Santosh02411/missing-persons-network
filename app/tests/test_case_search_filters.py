from app.models.user import UserRole

CASE_PAYLOAD = {
    "description": "Last seen near the central market wearing a blue jacket.",
    "last_seen_location": {"lat": 15.8497, "lng": 74.4977},
    "last_seen_address": "Central Market, Belagavi, Karnataka",
    "last_seen_at": "2026-07-01T10:00:00Z",
}


def _create_and_approve(client, reporter_headers, authority_headers, **overrides) -> dict:
    payload = {**CASE_PAYLOAD, **overrides}
    response = client.post("/api/v1/cases", json=payload, headers=reporter_headers)
    assert response.status_code == 201, response.text
    case = response.json()
    approve = client.post(f"/api/v1/cases/{case['id']}/approve", headers=authority_headers)
    assert approve.status_code == 200
    return approve.json()


def test_filter_by_gender(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    r_headers, a_headers = auth_headers(reporter), auth_headers(authority)

    case_f = _create_and_approve(client, r_headers, a_headers, name="Asha", gender="female")
    case_m = _create_and_approve(client, r_headers, a_headers, name="Rahul", gender="male")

    response = client.get("/api/v1/cases", params={"gender": "female"}, headers=r_headers)
    ids = [c["id"] for c in response.json()]
    assert case_f["id"] in ids
    assert case_m["id"] not in ids


def test_filter_by_age_range(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    r_headers, a_headers = auth_headers(reporter), auth_headers(authority)

    young = _create_and_approve(client, r_headers, a_headers, name="Kid", age_at_disappearance=8)
    old = _create_and_approve(client, r_headers, a_headers, name="Elder", age_at_disappearance=70)

    response = client.get("/api/v1/cases", params={"age_min": 5, "age_max": 12}, headers=r_headers)
    ids = [c["id"] for c in response.json()]
    assert young["id"] in ids
    assert old["id"] not in ids


def test_filter_by_last_seen_date_range(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    r_headers, a_headers = auth_headers(reporter), auth_headers(authority)

    early = _create_and_approve(client, r_headers, a_headers, name="Early", last_seen_at="2026-01-05T10:00:00Z")
    late = _create_and_approve(client, r_headers, a_headers, name="Late", last_seen_at="2026-07-20T10:00:00Z")

    response = client.get(
        "/api/v1/cases",
        params={"last_seen_after": "2026-01-01T00:00:00Z", "last_seen_before": "2026-02-01T00:00:00Z"},
        headers=r_headers,
    )
    ids = [c["id"] for c in response.json()]
    assert early["id"] in ids
    assert late["id"] not in ids


def test_filter_by_region(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    r_headers, a_headers = auth_headers(reporter), auth_headers(authority)

    belagavi = _create_and_approve(
        client, r_headers, a_headers, name="Belagavi Case", last_seen_address="MG Road, Belagavi, Karnataka"
    )
    mumbai = _create_and_approve(
        client, r_headers, a_headers, name="Mumbai Case", last_seen_address="Andheri, Mumbai, Maharashtra"
    )

    response = client.get("/api/v1/cases", params={"region": "Belagavi"}, headers=r_headers)
    ids = [c["id"] for c in response.json()]
    assert belagavi["id"] in ids
    assert mumbai["id"] not in ids


def test_filters_combine(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    r_headers, a_headers = auth_headers(reporter), auth_headers(authority)

    match = _create_and_approve(
        client, r_headers, a_headers, name="Match", gender="female", age_at_disappearance=20,
        last_seen_address="MG Road, Belagavi",
    )
    wrong_gender = _create_and_approve(
        client, r_headers, a_headers, name="WrongGender", gender="male", age_at_disappearance=20,
        last_seen_address="MG Road, Belagavi",
    )
    wrong_region = _create_and_approve(
        client, r_headers, a_headers, name="WrongRegion", gender="female", age_at_disappearance=20,
        last_seen_address="Andheri, Mumbai",
    )

    response = client.get(
        "/api/v1/cases",
        params={"gender": "female", "age_min": 18, "age_max": 25, "region": "Belagavi"},
        headers=r_headers,
    )
    ids = [c["id"] for c in response.json()]
    assert match["id"] in ids
    assert wrong_gender["id"] not in ids
    assert wrong_region["id"] not in ids


def test_different_filter_combos_dont_share_cache(client, make_user, auth_headers):
    """Regression guard: the cache key must incorporate every filter, or two
    different filter combinations would incorrectly return each other's
    cached results."""
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    r_headers, a_headers = auth_headers(reporter), auth_headers(authority)

    female = _create_and_approve(client, r_headers, a_headers, name="F", gender="female")
    male = _create_and_approve(client, r_headers, a_headers, name="M", gender="male")

    resp_f = client.get("/api/v1/cases", params={"gender": "female"}, headers=r_headers)
    resp_m = client.get("/api/v1/cases", params={"gender": "male"}, headers=r_headers)

    ids_f = [c["id"] for c in resp_f.json()]
    ids_m = [c["id"] for c in resp_m.json()]
    assert female["id"] in ids_f and male["id"] not in ids_f
    assert male["id"] in ids_m and female["id"] not in ids_m
