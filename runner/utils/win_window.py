# -*- coding: utf-8 -*-
from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Tuple

user32 = ctypes.WinDLL("user32", use_last_error=True)

GetForegroundWindow = user32.GetForegroundWindow
GetForegroundWindow.restype = wintypes.HWND

GetWindowRect = user32.GetWindowRect
GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
GetWindowRect.restype = wintypes.BOOL

GetClientRect = user32.GetClientRect
GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
GetClientRect.restype = wintypes.BOOL

ClientToScreen = user32.ClientToScreen
ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
ClientToScreen.restype = wintypes.BOOL


def get_foreground_hwnd() -> int:
    return int(GetForegroundWindow())


def get_window_rect(hwnd: int) -> Tuple[int, int, int, int]:
    r = wintypes.RECT()
    if not GetWindowRect(hwnd, ctypes.byref(r)):
        raise ctypes.WinError(ctypes.get_last_error())
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def get_client_rect_abs(hwnd: int) -> Tuple[int, int, int, int]:
    """
    Абсолютные координаты клиентской области окна (без рамок/тени), в пикселях экрана.
    """
    rc = wintypes.RECT()
    if not GetClientRect(hwnd, ctypes.byref(rc)):
        return get_window_rect(hwnd)

    # верхний левый клиент => экран
    pt = wintypes.POINT(rc.left, rc.top)
    if not ClientToScreen(hwnd, ctypes.byref(pt)):
        return get_window_rect(hwnd)

    width = rc.right - rc.left
    height = rc.bottom - rc.top
    return pt.x, pt.y, width, height


def get_active_client_bbox() -> Tuple[int, int, int, int]:
    """
    Совместимость: клиентская область текущего foreground-окна.
    """
    hwnd = get_foreground_hwnd()
    if hwnd == 0:
        raise RuntimeError("No foreground window")
    return get_client_rect_abs(hwnd)
