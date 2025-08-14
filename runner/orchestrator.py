# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict
from time import perf_counter, sleep
from rich.console import Console

from .context import Context
from .actions import REGISTRY  # импорт из __init__.py подтянет плагины
from .utils.timeparse import parse_duration


def run_scenario(cfg: Dict[str, Any], *, dry_run: bool = False) -> None:
    console = Console()
    ctx = Context(config=cfg, console=console, dry_run=dry_run)
    steps = cfg.get("steps") or []

    # глобальная пауза между шагами (необязательная)
    delay_between = (
        parse_duration(
            ((cfg.get("settings") or {}).get("defaults") or {}).get(
                "delay_between_steps"
            )
        )
        or 0.0
    )

    for idx, step in enumerate(steps, 1):
        name = step.get("name", f"step #{idx}")
        action = step.get("action")
        if not action:
            raise ValueError(f"Step #{idx} '{name}' has no 'action'")

        console.rule(f"[bold]Шаг {idx}[/] — {name}  ([dim]{action}[/])")

        # пер- и пост-задержки на уровне шага
        delay_before = parse_duration(step.get("delay_before"))
        delay_after = parse_duration(step.get("delay_after"))

        # «анонс» перед выполнением
        announce = step.get("announce")
        if announce:
            console.print(announce)

        if delay_before:
            sleep(delay_before)

        fn = REGISTRY.get(action)
        if not fn:
            raise KeyError(f"Unknown action: {action}")

        t0 = perf_counter()
        try:
            fn(ctx, step)
        except Exception:
            fail_msg = step.get("fail")
            if fail_msg:
                console.print(f"[red]{fail_msg}[/]")
            raise
        dt = perf_counter() - t0

        # успех
        success = step.get("success")
        if success:
            console.print(success)

        console.print(f"[green]OK[/] ({dt:.2f}s)")

        if delay_after:
            sleep(delay_after)

        if delay_between > 0:
            sleep(delay_between)
