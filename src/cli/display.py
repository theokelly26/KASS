"""Rich console formatting helpers for the KASS CLI."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# Shared theme for consistent styling across all CLI output.
KASS_THEME = Theme(
    {
        "buy_yes": "bold green",
        "buy_no": "bold red",
        "neutral": "dim",
        "regime.dead": "dim white",
        "regime.quiet": "cyan",
        "regime.active": "green",
        "regime.informed": "bold yellow",
        "regime.pre_settle": "bold magenta",
        "regime.unknown": "dim white",
        "ok": "bold green",
        "warning": "bold yellow",
        "critical": "bold red",
        "header": "bold cyan",
        "muted": "dim",
    }
)

console = Console(theme=KASS_THEME)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_price(cents: int | float | None) -> str:
    """Format a Kalshi price in cents (0-100) to a human-readable string."""
    if cents is None:
        return "--"
    return f"{int(cents)}\u00a2"


def format_direction(direction: str | None) -> Text:
    """Return a Rich Text object with the direction coloured appropriately."""
    if direction is None:
        return Text("--", style="dim")
    d = direction.lower()
    if d == "buy_yes":
        return Text("BUY YES", style="buy_yes")
    elif d == "buy_no":
        return Text("BUY NO", style="buy_no")
    else:
        return Text("NEUTRAL", style="neutral")


_REGIME_STYLES = {
    "dead": "regime.dead",
    "quiet": "regime.quiet",
    "active": "regime.active",
    "informed": "regime.informed",
    "pre_settle": "regime.pre_settle",
    "unknown": "regime.unknown",
}


def format_regime(regime: str | None) -> Text:
    """Return a Rich Text object for a market regime with colour coding."""
    if regime is None:
        return Text("--", style="dim")
    style = _REGIME_STYLES.get(regime.lower(), "dim")
    return Text(regime.upper(), style=style)


def format_status(ok: bool) -> Text:
    """Green checkmark for healthy, red X for unhealthy."""
    if ok:
        return Text("[OK]", style="ok")
    return Text("[FAIL]", style="critical")


def format_status_str(status: str) -> Text:
    """Colour a status string (ok / warning / critical)."""
    s = status.lower()
    if s == "ok":
        return Text("OK", style="ok")
    elif s == "warning":
        return Text("WARN", style="warning")
    elif s == "critical":
        return Text("CRIT", style="critical")
    return Text(status, style="dim")


def format_ts(ts) -> str:
    """Format a timestamp to a compact human-readable form."""
    if ts is None:
        return "--"
    try:
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    except AttributeError:
        return str(ts)


def format_age(age) -> str:
    """Format a timedelta to a compact string like '2m 14s' or '3h 5m'."""
    if age is None:
        return "--"
    try:
        total = int(age.total_seconds())
    except AttributeError:
        return str(age)
    if total < 0:
        return "--"
    if total < 60:
        return f"{total}s"
    if total < 3600:
        return f"{total // 60}m {total % 60}s"
    hours = total // 3600
    mins = (total % 3600) // 60
    return f"{hours}h {mins}m"


def format_float(val: float | None, decimals: int = 2) -> str:
    """Format a float with fixed decimal places, or '--' if None."""
    if val is None:
        return "--"
    return f"{val:.{decimals}f}"


# ---------------------------------------------------------------------------
# Reusable table builders
# ---------------------------------------------------------------------------

def create_signal_table(title: str = "Signals") -> Table:
    """Build a Rich Table pre-configured for signal display."""
    table = Table(title=title, show_lines=False, pad_edge=True)
    table.add_column("Time", style="muted", width=19)
    table.add_column("Type", style="header")
    table.add_column("Market", style="bold")
    table.add_column("Dir", width=8)
    table.add_column("Str", justify="right", width=5)
    table.add_column("Conf", justify="right", width=5)
    table.add_column("Urgency", width=10)
    return table


def create_market_table(title: str = "Markets") -> Table:
    """Build a Rich Table pre-configured for market overview display."""
    table = Table(title=title, show_lines=False, pad_edge=True)
    table.add_column("Ticker", style="bold")
    table.add_column("Price", justify="right", width=7)
    table.add_column("Spread", justify="right", width=7)
    table.add_column("Vol 24h", justify="right", width=9)
    table.add_column("OI", justify="right", width=9)
    table.add_column("Regime", width=12)
    table.add_column("Signals", justify="right", width=8)
    return table


def create_trade_table(title: str = "Trades") -> Table:
    """Build a Rich Table pre-configured for trade display."""
    table = Table(title=title, show_lines=False, pad_edge=True)
    table.add_column("Time", style="muted", width=19)
    table.add_column("Price", justify="right", width=7)
    table.add_column("Size", justify="right", width=8)
    table.add_column("Side", width=8)
    table.add_column("Trade ID", style="dim", width=20)
    return table
