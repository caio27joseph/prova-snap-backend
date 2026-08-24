"""Metrics setup — OpenTelemetry + Prometheus (T-13, Parte 4 melhoria nº 3).

Closes the gaps PARTE3_INCIDENT §5/§7 admitted: p95/p99 latency per endpoint,
DB query visibility, and audit-write failures as a metric instead of a log
line nobody reads. Everything is exposed on /metrics for Prometheus to scrape;
Grafana dashboards live in docker/grafana/ (compose profile `observability`).
"""

from fastapi import FastAPI, Response
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import Engine

# Instrument created at import time through the OTel API's proxy meter: it is
# a no-op until setup_observability() installs the real MeterProvider, and is
# transparently rebound afterwards. This keeps app.services.audit safe to
# import (and its counter safe to call) in any initialization order.
_meter = metrics.get_meter("prova-snap-backend")
audit_write_failures = _meter.create_counter(
    "audit_write_failures",
    unit="1",
    description="Audit-trail writes swallowed by the audit guard (search response preserved)",
)

_initialized = False


def setup_observability(app: FastAPI, engine: Engine) -> None:
    global _initialized
    if _initialized:
        # Idempotence guard: instrumenting twice (e.g. re-imports under test
        # runners) would double-count every request and re-register the
        # Prometheus collector, which raises on duplicate metric names.
        return
    _initialized = True

    # PrometheusMetricReader registers itself on prometheus_client's default
    # REGISTRY — the same registry make_asgi_app() serves below, so OTel
    # metrics and the endpoint need no extra wiring.
    metrics.set_meter_provider(
        MeterProvider(
            resource=Resource.create({"service.name": "search-api"}),
            metric_readers=[PrometheusMetricReader()],
        )
    )

    # Tracing is deliberately left unconfigured: the OTel API's default tracer
    # provider is a no-op, so the spans the instrumentors create cost nothing
    # and never error for lack of a collector. Only metrics are exported for
    # now; shipping spans (Tempo/Jaeger) is future work, not exam scope.

    # /health and /metrics are excluded from the HTTP histogram: probe and
    # scrape traffic every few seconds would drown out real user latency.
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics")
    # Query spans are no-ops (no tracer, see above), but the instrumentation
    # also emits DB connection-pool metrics, which is what the dashboard uses.
    SQLAlchemyInstrumentor().instrument(engine=engine)

    # Plain route with generate_latest() instead of mounting make_asgi_app():
    # a Starlette mount 307-redirects /metrics -> /metrics/, and the scrape
    # endpoint should answer exactly where Prometheus asks. Excluded from the
    # OpenAPI schema — /metrics is operational, not part of the API contract.
    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
