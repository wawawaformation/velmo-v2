"""Custom Chroma telemetry implementations for local runtime safety."""

from __future__ import annotations

from chromadb.telemetry.product import ProductTelemetryClient, ProductTelemetryEvent
from overrides import override


class NoOpProductTelemetry(ProductTelemetryClient):
    """Disable Chroma product telemetry events."""

    @override
    def capture(self, event: ProductTelemetryEvent) -> None:
        return
