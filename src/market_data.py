"""Market-data adapter seam.

Keep this tiny. Real provider wiring comes later.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QuoteResult:
    ticker: str
    return_pct: float | None = None
    market_value: float | None = None
    warning: str | None = None


@dataclass
class BenchmarkResult:
    benchmark: str
    return_pct: float | None = None
    warning: str | None = None


class MarketDataAdapter:
    """Provider boundary for quote and benchmark lookups."""

    async def fetch_quotes(self, positions: list[dict]) -> list[QuoteResult]:
        raise NotImplementedError

    async def fetch_benchmark(self, benchmark: str) -> BenchmarkResult:
        raise NotImplementedError
