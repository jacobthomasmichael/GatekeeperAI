"""
OpenTelemetry setup for GatekeeperAI.

Instruments FastAPI, SQLAlchemy, Celery, and Redis.
Exports via OTLP HTTP when OTEL_EXPORTER_OTLP_ENDPOINT is set;
falls back to a no-op provider in development so no collector is required.
"""

import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

logger = logging.getLogger(__name__)

_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "gatekeeperai")
_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")


def _build_exporter() -> SpanExporter | None:
    if not _OTLP_ENDPOINT:
        return None
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    return OTLPSpanExporter(endpoint=f"{_OTLP_ENDPOINT.rstrip('/')}/v1/traces")


def setup_telemetry(fastapi_app=None) -> TracerProvider:
    """
    Configure the global TracerProvider and instrument all supported libraries.
    Returns the provider so tests can inspect recorded spans.
    """
    resource = Resource(attributes={SERVICE_NAME: _SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    exporter = _build_exporter()
    if exporter:
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("OpenTelemetry: exporting to %s", _OTLP_ENDPOINT)
    else:
        logger.info("OpenTelemetry: no OTEL_EXPORTER_OTLP_ENDPOINT set — traces discarded")

    trace.set_tracer_provider(provider)

    # FastAPI
    if fastapi_app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(fastapi_app)

    # SQLAlchemy (instruments all engines created after this call)
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    SQLAlchemyInstrumentor().instrument()

    # Celery (instruments the default app and any app created after)
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    CeleryInstrumentor().instrument()

    # Redis
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    RedisInstrumentor().instrument()

    return provider
