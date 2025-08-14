# -*- coding: utf-8 -*-
from __future__ import annotations

import ctypes
from ctypes import wintypes
import time
from typing import Callable, Optional, Sequence

# user32 с корректной обработкой ошибок
user32 = ctypes.WinDLL("user32", use_last_error=True)

# ---- Совместимый алиас для ULONG_PTR ----
try:
    # На некоторых сборках есть, на некоторых — нет
    ULONG_PTR = wintypes.ULONG_PTR  # type: ignore[attr-defined]
except AttributeError:
    # Универсально: беззнаковый тип размера указателя
    ULONG_PTR = ctypes.c_size_t

# Константы
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D

# ---- Структуры для SendInput ----


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_union(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("iu", INPUT_union)]


# Сигнатуры WinAPI
user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT

# ---- Вспомогалки ----


def _send_inputs(batch: Sequence[INPUT]) -> None:
    arr = (INPUT * len(batch))(*batch)
    sent = user32.SendInput(len(batch), arr, ctypes.sizeof(INPUT))
    if sent != len(batch):
        raise ctypes.WinError(ctypes.get_last_error())


def send_unicode_char(ch: str) -> None:
    """Один Unicode-символ через KEYEVENTF_UNICODE."""
    code = ord(ch)
    down = INPUT(
        type=INPUT_KEYBOARD,
        iu=INPUT_union(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, 0)),
    )
    up = INPUT(
        type=INPUT_KEYBOARD,
        iu=INPUT_union(
            ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)
        ),
    )
    _send_inputs([down, up])


def _send_enter() -> None:
    down = INPUT(
        type=INPUT_KEYBOARD, iu=INPUT_union(ki=KEYBDINPUT(VK_RETURN, 0, 0, 0, 0))
    )
    up = INPUT(
        type=INPUT_KEYBOARD,
        iu=INPUT_union(ki=KEYBDINPUT(VK_RETURN, 0, KEYEVENTF_KEYUP, 0, 0)),
    )
    _send_inputs([down, up])


def send_unicode_text(
    text: str,
    per_char_delay: float = 0.0,
    delay_fn: Optional[Callable[[str], float]] = None,
) -> None:
    """
    Печатает строку по символам. \n отправляем как VK_RETURN — надёжнее для Win32-обычных окон.
    """
    for ch in text.replace("\r", "\n"):
        if ch == "\n":
            _send_enter()
        else:
            send_unicode_char(ch)

        if delay_fn is not None:
            time.sleep(max(0.0, float(delay_fn(ch))))
        elif per_char_delay > 0:
            time.sleep(per_char_delay)
