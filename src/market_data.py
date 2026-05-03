"""Market-data adapter seam with a yfinance-backed implementation."""

from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - exercised through degraded behavior
    yf = None


@dataclass
class QuoteResult:
    ticker: str
    current_price: float | None = None
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

    def fetch_quotes(self, positions: list[dict]) -> list[QuoteResult]:
        raise NotImplementedError

    def fetch_benchmark(self, benchmark: str) -> BenchmarkResult:
        raise NotImplementedError


class NullMarketDataAdapter(MarketDataAdapter):
    """Deterministic fallback when no provider is configured."""

    def fetch_quotes(self, positions: list[dict]) -> list[QuoteResult]:
        return [
            QuoteResult(
                ticker=position["ticker"],
                market_value=float(position.get("quantity", 0)) * float(position.get("avg_cost", 0)),
                warning="Live market data unavailable in this environment.",
            )
            for position in positions
        ]

    def fetch_benchmark(self, benchmark: str) -> BenchmarkResult:
        return BenchmarkResult(
            benchmark=benchmark,
            warning="Live benchmark data unavailable in this environment.",
        )


class YFinanceMarketDataAdapter(MarketDataAdapter):
    """Thin yfinance wrapper with bounded parallelism and graceful degradation."""

    BENCHMARK_SYMBOLS = {
        "FTSE 100": "^FTSE",
        "MSCI World": "URTH",
        "NIKKEI 225": "^N225",
        "QQQ": "QQQ",
        "S&P 500": "^GSPC",
    }

    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers

    def fetch_quotes(self, positions: list[dict]) -> list[QuoteResult]:
        if yf is None:
            return NullMarketDataAdapter().fetch_quotes(positions)

        with ThreadPoolExecutor(max_workers=min(self.max_workers, max(len(positions), 1))) as pool:
            return list(pool.map(self._quote_for_position, positions))

    def fetch_benchmark(self, benchmark: str) -> BenchmarkResult:
        if yf is None:
            return NullMarketDataAdapter().fetch_benchmark(benchmark)

        symbol = self.BENCHMARK_SYMBOLS.get(benchmark)
        if symbol is None:
            return BenchmarkResult(
                benchmark=benchmark,
                warning=f"No live symbol configured for benchmark {benchmark}.",
            )

        try:
            history = yf.Ticker(symbol).history(period="1mo", interval="1d", auto_adjust=True)
            if history.empty:
                return BenchmarkResult(
                    benchmark=benchmark,
                    warning=f"No benchmark history returned for {benchmark}.",
                )
            start = float(history["Close"].iloc[0])
            latest = float(history["Close"].iloc[-1])
            return_pct = ((latest - start) / start * 100) if start else None
            return BenchmarkResult(benchmark=benchmark, return_pct=round(return_pct, 2) if return_pct is not None else None)
        except Exception as exc:  # pragma: no cover - network/provider dependent
            return BenchmarkResult(
                benchmark=benchmark,
                warning=f"Benchmark lookup failed: {exc}",
            )

    def _quote_for_position(self, position: dict) -> QuoteResult:
        ticker = position["ticker"]
        average_cost = float(position.get("avg_cost", 0))
        quantity = float(position.get("quantity", 0))
        default_market_value = average_cost * quantity

        try:
            history = yf.Ticker(ticker).history(period="1mo", interval="1d", auto_adjust=True)
            if history.empty:
                return QuoteResult(
                    ticker=ticker,
                    market_value=round(default_market_value, 2),
                    warning=f"No quote history returned for {ticker}.",
                )

            latest_price = float(history["Close"].iloc[-1])
            return_pct = ((latest_price - average_cost) / average_cost * 100) if average_cost else None
            market_value = latest_price * quantity
            return QuoteResult(
                ticker=ticker,
                current_price=round(latest_price, 2),
                return_pct=round(return_pct, 2) if return_pct is not None else None,
                market_value=round(market_value, 2),
            )
        except Exception as exc:  # pragma: no cover - network/provider dependent
            return QuoteResult(
                ticker=ticker,
                market_value=round(default_market_value, 2),
                warning=f"Quote lookup failed: {exc}",
            )
