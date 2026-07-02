import os
from contextlib import contextmanager

# Safe imports for OpenTelemetry setup
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    
    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False

# Setup Tracer Provider
tracer = None
if HAS_OTEL:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    resource = Resource.create(attributes={"service.name": "aegis-evaluation-engine"})
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("aegis")
else:
    # Setup simple mock tracer class
    class MockSpan:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def set_attribute(self, key, value):
            pass
            
    class MockTracer:
        def start_as_current_span(self, name, *args, **kwargs):
            return MockSpan()
            
    tracer = MockTracer()

@contextmanager
def trace_span(span_name: str, attributes: dict = None):
    """Context manager wrapper to record tracing spans safely across evaluations."""
    with tracer.start_as_current_span(span_name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, str(v))
        yield span
