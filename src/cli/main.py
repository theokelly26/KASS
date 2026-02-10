"""KASS CLI entry point.

Usage:
    python -m src.cli.main [COMMAND] [OPTIONS]

Or via the installed console script:
    kass [COMMAND] [OPTIONS]
"""

from __future__ import annotations

import typer

from src.cli.commands import status, signals, markets, market, query, tail

app = typer.Typer(
    name="kass",
    help="KASS -- Kalshi Alpha Signal System CLI",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=True,
)

# Register sub-commands from each module.
app.command(name="status", help="System health dashboard")(status.status)
app.command(name="signals", help="View recent or live signals")(signals.signals)
app.command(name="markets", help="Market activity overview")(markets.markets)
app.command(name="market", help="Deep dive on a single market")(market.market)
app.command(name="query", help="Run a named analysis SQL query")(query.query)
app.command(name="tail", help="Tail a Redis stream in real time")(tail.tail)


if __name__ == "__main__":
    app()
