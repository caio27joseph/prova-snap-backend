"""Observability tests (ticket T-13): /metrics exposure and the audit-failure
counter.

What is reliably assertable in-process: the OTel MeterProvider is installed
once at app import, its Prometheus registry is cumulative for the whole test
session, and TestClient requests flow through the real instrumentation
middleware. So tests assert *deltas* between two /metrics reads, never
absolute values — other tests in the session also generate measurements.
"""

import re

from app.auth.mock_users import MARIA, MockUser
from app.observability import audit_write_failures
from tests.token_helpers import make_token

SEARCH_URL = "/api/v1/search"
HTTP_HISTOGRAM = "http_server_duration_milliseconds"
AUDIT_COUNTER = "audit_write_failures_total"


def _auth(user: MockUser) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user)}"}


def _metric_total(body: str, name: str, *required_labels: str) -> float:
    """Sum every sample of `name` whose label set contains all fragments —
    the exporter adds otel_scope_* labels, so exact-line matches are brittle."""
    total = 0.0
    for match in re.finditer(rf"^{name}(?:{{([^}}]*)}})? ([0-9.e+-]+)$", body, re.MULTILINE):
        labels = match.group(1) or ""
        if all(fragment in labels for fragment in required_labels):
            total += float(match.group(2))
    return total


def test_metrics_endpoint_exposes_expected_metric_names(client):
    # A counter only appears in the exposition after its first data point;
    # add(0) forces one without pretending a failure happened.
    audit_write_failures.add(0)
    # Same for the HTTP histogram: one real (non-excluded) request guarantees it.
    client.post(SEARCH_URL, json={"query": "contas"}, headers=_auth(MARIA))

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert HTTP_HISTOGRAM in response.text
    assert AUDIT_COUNTER in response.text
    # SQLAlchemy instrumentation: pool gauge feeds the dashboard's DB panel.
    assert "db_client_connections_usage_connections" in response.text


def test_search_request_is_recorded_in_http_histogram(client):
    route_label = f'http_target="{SEARCH_URL}"'
    before = _metric_total(client.get("/metrics").text, f"{HTTP_HISTOGRAM}_count", route_label)

    search = client.post(SEARCH_URL, json={"query": "contas"}, headers=_auth(MARIA))
    assert search.status_code == 200

    after = _metric_total(client.get("/metrics").text, f"{HTTP_HISTOGRAM}_count", route_label)
    # Exactly +1: /metrics itself is excluded from instrumentation, so the
    # two reads bracketing the search add nothing to the histogram.
    assert after == before + 1


def test_audit_failure_increments_counter(client, db_session, monkeypatch):
    def _commit_fails():
        raise RuntimeError("simulated audit commit failure")

    before = _metric_total(client.get("/metrics").text, AUDIT_COUNTER)

    # Same failure injection as test_error_paths: audit._write is the only
    # commit in the request path, so breaking commit hits the audit guard only.
    monkeypatch.setattr(db_session, "commit", _commit_fails)
    response = client.post(SEARCH_URL, json={"query": "contas"}, headers=_auth(MARIA))

    assert response.status_code == 200  # the guard held: search unaffected
    after = _metric_total(client.get("/metrics").text, AUDIT_COUNTER)
    assert after == before + 1
