"""
Tests for OpenTelemetry instrumentation.

OTel only allows setting the global TracerProvider once. app.main sets it at
import time (conftest imports app.main), so tests that need span recording
use the provider directly rather than fighting the global registry.
"""

import os
import pytest
from unittest.mock import patch

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME


# ── helpers ───────────────────────────────────────────────────────────────────

def _provider_with_exporter() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Standalone provider+exporter pair, independent of the global registry."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _add_exporter_to_global() -> InMemorySpanExporter:
    """Attach an InMemorySpanExporter to the already-set global provider."""
    exporter = InMemorySpanExporter()
    global_provider = trace.get_tracer_provider()
    global_provider.add_span_processor(SimpleSpanProcessor(exporter))  # type: ignore[attr-defined]
    return exporter


# ── provider / resource tests ─────────────────────────────────────────────────

class TestSetupTelemetry:
    def test_returns_tracer_provider(self):
        from app.telemetry import setup_telemetry
        # setup_telemetry was already called by app.main import; calling again
        # returns the existing provider (OTel ignores the second set_tracer_provider).
        provider = setup_telemetry()
        assert isinstance(provider, TracerProvider)

    def test_global_tracer_provider_is_sdk_provider(self):
        # Confirm the global provider is our SDK provider (not the no-op default).
        global_provider = trace.get_tracer_provider()
        assert isinstance(global_provider, TracerProvider)

    def test_service_name_in_resource(self):
        from app.telemetry import setup_telemetry
        provider = setup_telemetry()
        attrs = provider.resource.attributes
        assert attrs.get(SERVICE_NAME) == "gatekeeperai"

    def test_no_otlp_endpoint_does_not_raise(self):
        """setup_telemetry with no endpoint configured should not raise."""
        from app.telemetry import setup_telemetry
        import app.telemetry as tel_mod
        original = tel_mod._OTLP_ENDPOINT
        tel_mod._OTLP_ENDPOINT = ""
        try:
            provider = setup_telemetry()
            assert isinstance(provider, TracerProvider)
        finally:
            tel_mod._OTLP_ENDPOINT = original

    def test_otlp_endpoint_builds_exporter(self):
        """When OTLP endpoint is set, _build_exporter returns an OTLPSpanExporter."""
        from app.telemetry import _build_exporter
        import app.telemetry as tel_mod

        original = tel_mod._OTLP_ENDPOINT
        tel_mod._OTLP_ENDPOINT = "http://otel-collector:4318"
        try:
            exporter = _build_exporter()
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            assert isinstance(exporter, OTLPSpanExporter)
        finally:
            tel_mod._OTLP_ENDPOINT = original

    def test_no_otlp_endpoint_returns_none(self):
        from app.telemetry import _build_exporter
        import app.telemetry as tel_mod

        original = tel_mod._OTLP_ENDPOINT
        tel_mod._OTLP_ENDPOINT = ""
        try:
            assert _build_exporter() is None
        finally:
            tel_mod._OTLP_ENDPOINT = original

    def test_service_name_from_env_var(self):
        """_SERVICE_NAME module constant is read from OTEL_SERVICE_NAME at import."""
        import app.telemetry as tel_mod
        original = tel_mod._SERVICE_NAME
        tel_mod._SERVICE_NAME = "custom-service"
        try:
            provider = tel_mod.setup_telemetry()
            assert provider.resource.attributes.get(SERVICE_NAME) == "custom-service"
        finally:
            tel_mod._SERVICE_NAME = original


# ── span recording tests (use provider directly, not global) ──────────────────

class TestSpanRecording:
    def test_manual_span_recorded(self):
        """Spans created via a standalone provider land in its exporter."""
        provider, exporter = _provider_with_exporter()
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span("test-op") as span:
            span.set_attribute("test.key", "value")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test-op"
        assert spans[0].attributes["test.key"] == "value"

    def test_span_status_unset_by_default(self):
        provider, exporter = _provider_with_exporter()
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("noop"):
            pass

        from opentelemetry.trace import StatusCode
        assert exporter.get_finished_spans()[0].status.status_code == StatusCode.UNSET

    def test_span_records_exception(self):
        provider, exporter = _provider_with_exporter()
        tracer = provider.get_tracer("test")

        with pytest.raises(ValueError):
            with tracer.start_as_current_span("failing-op") as span:
                try:
                    raise ValueError("boom")
                except ValueError:
                    span.record_exception(ValueError("boom"))
                    raise

        events = exporter.get_finished_spans()[0].events
        assert any(e.name == "exception" for e in events)

    def test_nested_spans_have_parent(self):
        provider, exporter = _provider_with_exporter()
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span("parent"):
            with tracer.start_as_current_span("child"):
                pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 2
        child = next(s for s in spans if s.name == "child")
        parent = next(s for s in spans if s.name == "parent")
        assert child.parent is not None
        assert child.parent.span_id == parent.context.span_id

    def test_multiple_spans_share_trace_id(self):
        provider, exporter = _provider_with_exporter()
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span("root") as root:
            trace_id = root.context.trace_id
            with tracer.start_as_current_span("branch"):
                pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 2
        assert all(s.context.trace_id == trace_id for s in spans)

    def test_span_attribute_types(self):
        """Spans accept str, int, float, and bool attributes."""
        provider, exporter = _provider_with_exporter()
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span("typed") as span:
            span.set_attribute("str_attr", "hello")
            span.set_attribute("int_attr", 42)
            span.set_attribute("float_attr", 3.14)
            span.set_attribute("bool_attr", True)

        attrs = exporter.get_finished_spans()[0].attributes
        assert attrs["str_attr"] == "hello"
        assert attrs["int_attr"] == 42
        assert attrs["float_attr"] == pytest.approx(3.14)
        assert attrs["bool_attr"] is True


# ── FastAPI integration ────────────────────────────────────────────────────────

class TestFastAPIInstrumentation:
    def test_setup_with_fastapi_app_does_not_raise(self):
        from fastapi import FastAPI
        from app.telemetry import setup_telemetry
        # setup_telemetry with a FastAPI app should not raise even if provider
        # is already set (it just warns and returns the existing provider).
        dummy = FastAPI()
        provider = setup_telemetry(fastapi_app=dummy)
        assert isinstance(provider, TracerProvider)

    def test_health_route_produces_span(self):
        """Requests to a FastAPI route should produce at least one server span."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        dummy = FastAPI()

        @dummy.get("/ping")
        def ping():
            return {"status": "ok"}

        # Attach exporter to the already-set global provider, then instrument.
        exporter = _add_exporter_to_global()
        FastAPIInstrumentor.instrument_app(dummy)

        try:
            client = TestClient(dummy, raise_server_exceptions=False)
            resp = client.get("/ping")
            assert resp.status_code == 200

            spans = exporter.get_finished_spans()
            assert len(spans) >= 1
            assert any("ping" in s.name.lower() or "GET" in s.name for s in spans)
        finally:
            FastAPIInstrumentor.uninstrument_app(dummy)
