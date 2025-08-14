# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table

from .dsl import load_config, validate_scenario
from .orchestrator import run_scenario


app = typer.Typer(add_completion=False, help="Mini-RPA Runner (skeleton)")

console = Console()
ROOT = Path(__file__).resolve().parents[1]


def _iter_scenarios() -> List[Path]:
    folder = ROOT / "scenarios"
    if not folder.exists():
        return []
    return sorted(folder.glob("*.yaml"))


@app.command(name="list")
def list_scenarios() -> None:
    """Показать сценарии из каталога scenarios/"""
    rows = _iter_scenarios()
    if not rows:
        console.print("[yellow]Сценариев пока нет.[/]")
        raise typer.Exit(code=0)
    table = Table(title="Доступные сценарии")
    table.add_column("Имя")
    table.add_column("Путь")
    for p in rows:
        table.add_row(p.stem, str(p))
    console.print(table)


@app.command()
def check(
    scenario: str = typer.Argument(..., help="Путь к yaml или имя из папки scenarios"),
    profile: Optional[str] = typer.Option(None, help="Имя профиля из configs/profiles"),
    override: List[str] = typer.Option(
        None, "--set", help="Переопределения key=value (можно несколько)"
    ),
) -> None:
    """Проверить сценарий: загрузка + базовая валидация DSL."""
    cfg = load_config(ROOT, scenario, profile, override or [])
    errors = validate_scenario(cfg)
    if errors:
        console.print("[red]Ошибки:[/]")
        for e in errors:
            console.print(f" - {e}")
        raise typer.Exit(code=2)
    steps = cfg.get("steps", [])
    console.print(f"[green]OK[/]: версия={cfg.get('version')} шагов={len(steps)}")


@app.command()
def run(
    scenario: str = typer.Argument(..., help="Путь к yaml или имя из папки scenarios"),
    profile: Optional[str] = typer.Option(None, help="Имя профиля из configs/profiles"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Ничего не исполнять, только прогнать конфиг"
    ),
    override: List[str] = typer.Option(
        None, "--set", help="Переопределения key=value (можно несколько)"
    ),
) -> None:
    """
    Выполнить сценарий: грузим конфиг, печатаем сводку, затем исполняем (или dry-run).
    """
    cfg = load_config(ROOT, scenario, profile, override or [])
    errors = validate_scenario(cfg)
    if errors:
        console.print("[red]Ошибки:[/]")
        for e in errors:
            console.print(f" - {e}")
        raise typer.Exit(code=2)

    steps = cfg.get("steps", [])
    console.rule("[bold cyan]Сводка")
    console.print(f"Версия: {cfg.get('version')}")
    console.print(f"Шагов: {len(steps)}")
    console.print(f"Dry-run: {dry_run}")

    run_scenario(cfg, dry_run=dry_run)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
