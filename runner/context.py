# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict
from rich.console import Console


@dataclass
class Context:
    """
    Выполнение одного сценария. Содержит конфиг, консоль логов,
    флаг dry_run и общее состояние (state) между шагами.
    """

    config: Dict[str, Any]
    console: Console
    dry_run: bool = False
    state: Dict[str, Any] = field(default_factory=dict)
