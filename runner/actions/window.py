# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import time
import ctypes
from ctypes import wintypes
from typing import Any, Dict, Optional, Tuple

from ..context import Context
from . import register

# WinAPI
user32 = ctypes.WinDLL("user32", use_last_error=True)

GetWindowTextW = user32.GetWindowTextW
GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
GetWindowTextW.restype = ctypes.c_int

GetWindowTextLengthW = user32.GetWindowTextLengthW
GetWindowTextLengthW.argtypes = (wintypes.HWND,)
GetWindowTextLengthW.restype = ctypes.c_int

GetClassNameW = user32.GetClassNameW
GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
GetClassNameW.restype = ctypes.c_int

IsWindowVisible = user32.IsWindowVisible
IsWindowVisible.argtypes = (wintypes.HWND,)
IsWindowVisible.restype = wintypes.BOOL

EnumWindows = user32.EnumWindows
EnumWindows.restype = wintypes.BOOL  # сигнатуру колбэка зададим ниже

SetForegroundWindow = user32.SetForegroundWindow
SetForegroundWindow.argtypes = (wintypes.HWND,)
SetForegroundWindow.restype = wintypes.BOOL

ShowWindow = user32.ShowWindow
ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
ShowWindow.restype = wintypes.BOOL

SW_RESTORE = 9


def _parse_regex(expr: str) -> re.Pattern:
    """
    Поддержка '/.../i' или обычной строки (как подстроки, без спецсимволов).
    """
    if not isinstance(expr, str):
        raise ValueError("regex must be string")
    if len(expr) >= 2 and expr[0] == "/" and expr.rfind("/") > 0:
        last = expr.rfind("/")
        body = expr[1:last]
        flags_raw = expr[last + 1 :]
        flags = re.IGNORECASE if "i" in flags_raw else 0
        return re.compile(body, flags)
    return re.compile(re.escape(expr), re.IGNORECASE)


def _get_text(hwnd: int) -> str:
    n = GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    GetWindowTextW(hwnd, buf, n + 1)
    return buf.value or ""


def _get_class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    GetClassNameW(hwnd, buf, 256)
    return buf.value or ""


def _enum_windows() -> list[Tuple[int, str, str]]:
    items: list[Tuple[int, str, str]] = []

    # BOOL CALLBACK EnumWindowsProc(HWND hwnd, LPARAM lParam)
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, lparam):
        try:
            if not IsWindowVisible(hwnd):
                return True
            title = _get_text(hwnd)
            if not title:
                return True
            cls = _get_class(hwnd)
            items.append((int(hwnd), title, cls))
        except Exception:
            # не роняем перечисление
            pass
        return True

    cb = EnumWindowsProc(_cb)
    if not EnumWindows(cb, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return items


def _find_window(
    title_re: re.Pattern, class_re: Optional[re.Pattern]
) -> Optional[Tuple[int, str]]:
    for hwnd, title, cls in _enum_windows():
        if not title_re.search(title):
            continue
        if class_re and not class_re.search(cls):
            continue
        return hwnd, title
    return None


@register("wait_window")
def wait_window(ctx: Context, step: Dict[str, Any]) -> None:
    """
    params:
      title: regex '/.../i' или строка
      class?: regex '/.../i'
      timeout?: duration
    """
    from ..utils.timeparse import parse_duration

    title_expr = step.get("title")
    if not title_expr:
        raise ValueError("wait_window: 'title' is required")
    class_expr = step.get("class")

    title_re = _parse_regex(str(title_expr))
    class_re = _parse_regex(str(class_expr)) if class_expr else None

    timeout = (
        parse_duration(step.get("timeout"))
        or parse_duration((ctx.config.get("window") or {}).get("focus_timeout"))
        or 10.0
    )

    ctx.console.print(f"Жду окно: '{title_expr}' (до {timeout:.1f}s)...")
    t0 = time.perf_counter()
    deadline = t0 + timeout
    while time.perf_counter() < deadline:
        hit = _find_window(title_re, class_re)
        if hit:
            hwnd, title = hit
            dt = time.perf_counter() - t0
            ctx.console.print(f"Нашёл '{title}' за {dt:.2f}s")
            # полезно запомнить
            ctx.state["target_hwnd"] = int(hwnd)
            return
        time.sleep(0.1)
    raise TimeoutError(f"wait_window: не найдено окно '{title_expr}' за {timeout:.1f}s")


@register("window_focus")
def window_focus(ctx: Context, step: Dict[str, Any]) -> None:
    """
    params:
      title: regex '/.../i' или строка
      class?: regex
      timeout?: duration (на поиск окна)
    """
    from ..utils.timeparse import parse_duration

    title_expr = step.get("title")
    if not title_expr:
        raise ValueError("window_focus: 'title' is required")
    class_expr = step.get("class")

    title_re = _parse_regex(str(title_expr))
    class_re = _parse_regex(str(class_expr)) if class_expr else None

    timeout = parse_duration(step.get("timeout")) or 5.0
    t0 = time.perf_counter()
    deadline = t0 + timeout

    hwnd_title: Optional[Tuple[int, str]] = None
    while time.perf_counter() < deadline:
        hit = _find_window(title_re, class_re)
        if hit:
            hwnd_title = hit
            break
        time.sleep(0.1)

    if not hwnd_title:
        raise TimeoutError(f"window_focus: окно '{title_expr}' не найдено")

    hwnd, title = hwnd_title
    # восстановим и выведем на передний план
    ShowWindow(hwnd, SW_RESTORE)
    if not SetForegroundWindow(hwnd):
        time.sleep(0.05)
        SetForegroundWindow(hwnd)

    ctx.state["target_hwnd"] = int(hwnd)  # ключ: Vision будет искать в этом окне
    ctx.console.print(f"Фокус на: '{title}'")
