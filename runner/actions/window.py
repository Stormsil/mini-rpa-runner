# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional

import pygetwindow as gw

from ..utils.timeparse import parse_duration
from ..context import Context
from . import register


def _compile_regex(pat: str) -> re.Pattern[str]:
    """
    Поддержка двух форматов:
      - "/regex/i"  (с флагом i = ignore case)
      - обычная строка => ищется как подстрока без учета регистра
    """
    s = pat.strip()
    if len(s) >= 2 and s[0] == "/" and s.rfind("/") > 0:
        last = s.rfind("/")
        body = s[1:last]
        flags_str = s[last + 1 :].lower()
        flags = re.IGNORECASE if "i" in flags_str else 0
        return re.compile(body, flags)
    return re.compile(re.escape(s), re.IGNORECASE)


def _find_window(title_pat: re.Pattern[str]) -> Optional[gw.Window]:
    for w in gw.getAllWindows():
        try:
            t = w.title or ""
        except Exception:
            t = ""
        if title_pat.search(t):
            return w
    return None


@register("wait_window")
def wait_window(ctx: Context, step: Dict[str, Any]) -> None:
    """
    params:
      title: str (regex или строка)
      exists?: bool = true
      timeout?: duration (наследует defaults.timeout)
    """
    title = step.get("title")
    if not title:
        raise ValueError("wait_window: 'title' is required")
    exists = bool(step.get("exists", True))
    timeout = parse_duration(step.get("timeout") or ctx.defaults.get("timeout")) or 15.0

    pat = _compile_regex(str(title))
    deadline = time.time() + timeout

    while time.time() < deadline:
        w = _find_window(pat)
        if exists and w is not None:
            return
        if not exists and w is None:
            return
        time.sleep(0.25)

    state = "appear" if exists else "disappear"
    raise TimeoutError(f"wait_window: timeout waiting for window to {state}: {title}")


@register("window_focus")
def window_focus(ctx: Context, step: Dict[str, Any]) -> None:
    """
    params:
      title: str (regex или строка)
    """
    title = step.get("title")
    if not title:
        raise ValueError("window_focus: 'title' is required")

    pat = _compile_regex(str(title))
    w = _find_window(pat)
    if not w:
        raise RuntimeError(f"window_focus: window not found: {title}")

    if ctx.dry_run:
        ctx.console.print(f"[cyan]DRY[/] window_focus: '{w.title}'")
        return

    try:
        if getattr(w, "isMinimized", False):
            w.restore()
        w.activate()
    except Exception as e:
        raise RuntimeError(f"window_focus: failed to focus '{w.title}': {e}")
