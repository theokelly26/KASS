"""kass query <name> -- Run a named analysis SQL query.

Loads .sql files from analysis/queries/ and runs them against the database,
presenting results as Rich tables.

Available queries:
    system_health      01_system_health.sql
    signal_overview    02_signal_overview.sql
    signal_quality     03_signal_quality.sql
    threshold_tuning   04_threshold_tuning.sql
    market_deep_dive   05_market_deep_dive.sql
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.table import Table

from src.cli.display import console


# Map of friendly query names to SQL filenames.
QUERY_MAP: dict[str, str] = {
    "system_health": "01_system_health.sql",
    "signal_overview": "02_signal_overview.sql",
    "signal_quality": "03_signal_quality.sql",
    "threshold_tuning": "04_threshold_tuning.sql",
    "market_deep_dive": "05_market_deep_dive.sql",
}

# Base directory for analysis SQL files (relative to project root).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_QUERIES_DIR = _PROJECT_ROOT / "analysis" / "queries"


def _list_available() -> None:
    """Print available query names and whether the SQL file exists."""
    table = Table(title="Available Queries", show_lines=False, pad_edge=True)
    table.add_column("Name", style="bold")
    table.add_column("File")
    table.add_column("Status")

    for name, filename in QUERY_MAP.items():
        path = _QUERIES_DIR / filename
        exists = path.exists()
        table.add_row(
            name,
            filename,
            "[green]found[/green]" if exists else "[red]missing[/red]",
        )
    console.print(table)


def _split_statements(sql_text: str) -> list[str]:
    """
    Split an SQL file into individual statements.

    Simple heuristic: split on semicolons that are not inside comments.
    Each statement is stripped; empty ones are discarded.
    """
    statements: list[str] = []
    current: list[str] = []
    in_block_comment = False

    for line in sql_text.splitlines():
        stripped = line.strip()

        # Handle block comments
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            in_block_comment = True
            continue

        # Skip single-line comments
        if stripped.startswith("--"):
            continue

        current.append(line)

        # Check if line ends a statement
        if stripped.endswith(";"):
            stmt = "\n".join(current).strip().rstrip(";").strip()
            if stmt:
                statements.append(stmt)
            current = []

    # Catch any trailing statement without a semicolon
    if current:
        stmt = "\n".join(current).strip().rstrip(";").strip()
        if stmt:
            statements.append(stmt)

    return statements


async def _run_query(config, sql_text: str) -> None:
    """Execute all statements in an SQL file and display results."""
    from src.persistence.db import get_connection

    statements = _split_statements(sql_text)

    if not statements:
        console.print("[yellow]No executable statements found in the SQL file.[/yellow]")
        return

    async with get_connection(config.postgres) as conn:
        for idx, stmt in enumerate(statements, 1):
            # Show a short preview of the statement
            preview = stmt.strip().splitlines()[0][:80]
            console.print(f"\n[bold cyan]Statement {idx}:[/bold cyan] {preview}")

            try:
                async with conn.cursor() as cur:
                    await cur.execute(stmt)

                    if cur.description is None:
                        # Non-SELECT statement (DDL, etc.)
                        console.print(f"  [dim]OK (no result set)[/dim]")
                        continue

                    columns = [desc[0] for desc in cur.description]
                    rows = await cur.fetchall()

                    if not rows:
                        console.print("  [dim]Query returned 0 rows.[/dim]")
                        continue

                    table = Table(show_lines=False, pad_edge=True)
                    for col in columns:
                        table.add_column(col, overflow="fold")

                    for row in rows:
                        table.add_row(*[_format_cell(v) for v in row])

                    console.print(table)
                    console.print(f"  [dim]{len(rows)} row(s)[/dim]")

            except Exception as e:
                console.print(f"  [red]Error:[/red] {e}")


def _format_cell(value) -> str:
    """Convert a DB cell to a display string."""
    if value is None:
        return "--"
    if isinstance(value, float):
        return f"{value:.4f}" if abs(value) < 1000 else f"{value:,.1f}"
    return str(value)


# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------

async def _query_async(name: str) -> None:
    from src.config import get_config
    from src.persistence.db import close_pool

    config = get_config()

    # Resolve the query
    filename = QUERY_MAP.get(name)
    if filename is None:
        # Maybe the user passed the filename directly
        path = _QUERIES_DIR / name
        if not path.exists() and not name.endswith(".sql"):
            path = _QUERIES_DIR / f"{name}.sql"
        if not path.exists():
            console.print(f"[red]Unknown query:[/red] '{name}'")
            console.print()
            _list_available()
            return
    else:
        path = _QUERIES_DIR / filename

    if not path.exists():
        console.print(f"[red]SQL file not found:[/red] {path}")
        console.print("[dim]The analysis/queries/ directory may need additional SQL files.[/dim]")
        console.print()
        _list_available()
        return

    sql_text = path.read_text()
    console.print(f"[bold]Running:[/bold] {path.name}")

    try:
        await _run_query(config, sql_text)
    except Exception as e:
        console.print(f"[red]Query execution failed:[/red] {e}")
    finally:
        await close_pool()


def query(
    name: str = typer.Argument(
        ...,
        help="Query name (system_health, signal_overview, signal_quality, threshold_tuning, market_deep_dive) or SQL filename",
    ),
) -> None:
    """Run a named analysis SQL query and display results as tables."""
    asyncio.run(_query_async(name))
