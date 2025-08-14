# -*- coding: utf-8 -*-
from __future__ import annotations

import random
import sys
import time
from typing import Any, Dict, List, Optional

import pyautogui as pag
import pyperclip

from ..utils.timeparse import parse_duration
from ..context import Context
from ..utils.win_unicode import send_unicode_text, send_unicode_char
from . import register


def _keys_list(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, (list, tuple)):
        return [str(x) for x in val]
    return [str(val)]


def _contains_non_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return False
    except UnicodeEncodeError:
        return True


# ---------------------------
# "Человечный" профиль ввода
# ---------------------------


def _pick_speed_cps(speed: Any) -> Optional[float]:
    if speed is None:
        return None
    if isinstance(speed, (int, float)) and speed > 0:
        return float(speed)
    if isinstance(speed, (list, tuple)) and len(speed) == 2:
        a, b = float(speed[0]), float(speed[1])
        lo, hi = min(a, b), max(a, b)
        if lo <= 0:
            return None
        return random.uniform(lo, hi)
    return None


def _rand_ms(lo: float, hi: float) -> float:
    if hi < lo:
        lo, hi = hi, lo
    return random.uniform(lo, hi) / 1000.0


def _pick_ms_range(val: Any, fallback: tuple[float, float] = (0.0, 0.0)) -> float:
    lo, hi = fallback
    if isinstance(val, (list, tuple)) and len(val) == 2:
        lo, hi = float(val[0]), float(val[1])
    if lo == hi == 0.0:
        return 0.0
    return _rand_ms(lo, hi)


def _human_delay_for_char(ch: str, h: Dict[str, Any]) -> float:
    delay = 0.0
    cps = _pick_speed_cps(h.get("speed_cps"))
    if cps and cps > 0:
        delay += 1.0 / cps
    delay += _pick_ms_range(h.get("jitter_ms"), (0.0, 0.0))
    if ch in (" ", "\t"):
        delay += _pick_ms_range(h.get("word_pause_ms"), (0.0, 0.0))
    elif ch in ".!,?:;-–—)]}":
        delay += _pick_ms_range(h.get("punct_pause_ms"), (0.0, 0.0))
    elif ch == "\n":
        delay += _pick_ms_range(h.get("newline_pause_ms"), (120.0, 280.0))
    return max(0.0, delay)


def _maybe_mistype_and_fix(ch: str, h: Dict[str, Any], backend: str) -> Optional[str]:
    m = h.get("mistakes") or {}
    prob = float(m.get("prob", 0.0))
    if prob <= 0.0 or random.random() > prob:
        return None
    charset = str(m.get("charset", "abcdefghijklmnopqrstuvwxyz"))
    if not charset or ch in "\n\t ":
        return None
    wrong = random.choice(charset)
    # для win_unicode тоже ок — отправим Unicode-символ и затем Backspace
    return wrong


def _backend_for_text(step: Dict[str, Any], text: str) -> str:
    be = (step.get("backend") or "auto").lower()
    if be == "auto":
        if sys.platform == "win32" and _contains_non_ascii(text):
            return "win_unicode"
        return "pyautogui"
    if be in ("pyautogui", "win_unicode", "clipboard"):
        return be
    return "pyautogui"


@register("type_text")
def type_text(ctx: Context, step: Dict[str, Any]) -> None:
    """
    params:
      text: str
      per_char_delay?: duration
      backend?: auto|pyautogui|win_unicode|clipboard
      humanize?: {
        speed_cps: 10 | [8,12],
        jitter_ms: [15,60],
        word_pause_ms: [80,180],
        punct_pause_ms: [120,260],
        newline_pause_ms: [150,300],
        start_pause_ms: [100,300],
        mistakes: { prob: 0.0..1.0, fix_with_backspace: true, charset: "..." }
      }

    Также читаются глобальные дефолты: config.input.humanize_defaults
    (мерджатся со значениями из шага; шаг перекрывает конфиг).
    """
    text = step.get("text")
    if text is None:
        raise ValueError("type_text: 'text' is required")
    text = str(text)

    # бэкенд
    backend = _backend_for_text(step, text)

    # humanize или детерминированная задержка
    human = step.get("humanize")
    base_delay = None
    if human is None:
        base_delay = parse_duration(step.get("per_char_delay"))
        if base_delay is None:
            base_delay = parse_duration(
                (ctx.config.get("input") or {}).get("type_delay")
            )
        if base_delay is None:
            base_delay = 0.0

    if ctx.dry_run:
        if human is not None:
            cfg_input = ctx.config.get("input") or {}
            g = cfg_input.get("humanize_defaults") or {}
            h_show = {**g, **(human or {})}
            ctx.console.print(
                f"[cyan]DRY[/] type_text ({backend}, humanize): len={len(text)} cfg={h_show}"
            )
        else:
            ctx.console.print(
                f"[cyan]DRY[/] type_text ({backend}): len={len(text)} delay={base_delay:.3f}s"
            )
        return

    pag.FAILSAFE = False

    def _type_char(ch: str) -> None:
        if backend == "pyautogui":
            pag.write(ch)
        elif backend == "win_unicode":
            send_unicode_char(ch)
        elif backend == "clipboard":
            raise RuntimeError("clipboard backend does not support char-by-char typing")

    # HUMANIZE РЕЖИМ
    if human is not None:
        cfg_input = ctx.config.get("input") or {}
        g = cfg_input.get("humanize_defaults") or {}
        m_step = (human.get("mistakes") or {}) if isinstance(human, dict) else {}
        m_glob = (g.get("mistakes") or {}) if isinstance(g, dict) else {}

        # Мердж дефолтов (глобальные → шаг)
        h = {
            "speed_cps": (
                human.get("speed_cps")
                if isinstance(human, dict) and "speed_cps" in human
                else g.get("speed_cps", [8, 12])
            ),
            "jitter_ms": (
                human.get("jitter_ms")
                if isinstance(human, dict) and "jitter_ms" in human
                else g.get("jitter_ms", [15, 60])
            ),
            "word_pause_ms": (
                human.get("word_pause_ms")
                if isinstance(human, dict) and "word_pause_ms" in human
                else g.get("word_pause_ms", [80, 180])
            ),
            "punct_pause_ms": (
                human.get("punct_pause_ms")
                if isinstance(human, dict) and "punct_pause_ms" in human
                else g.get("punct_pause_ms", [120, 260])
            ),
            "newline_pause_ms": (
                human.get("newline_pause_ms")
                if isinstance(human, dict) and "newline_pause_ms" in human
                else g.get("newline_pause_ms", [150, 300])
            ),
            "start_pause_ms": (
                human.get("start_pause_ms")
                if isinstance(human, dict) and "start_pause_ms" in human
                else g.get("start_pause_ms", [120, 300])
            ),
            "mistakes": {  # глубинный мердж
                "prob": m_step.get("prob", m_glob.get("prob", 0.0)),
                "fix_with_backspace": m_step.get(
                    "fix_with_backspace", m_glob.get("fix_with_backspace", True)
                ),
                "charset": m_step.get(
                    "charset", m_glob.get("charset", "abcdefghijklmnopqrstuvwxyz")
                ),
            },
        }

        # небольшая стартовая пауза (как будто человек «перехватил» фокус)
        sp = h.get("start_pause_ms")
        if isinstance(sp, (list, tuple)) and len(sp) == 2:
            time.sleep(_rand_ms(float(sp[0]), float(sp[1])))

        for ch in text:
            wrong = _maybe_mistype_and_fix(ch, h, backend)
            if wrong:
                _type_char(wrong)
                time.sleep(_rand_ms(40.0, 90.0))
                pag.press("backspace")

            _type_char(ch)
            time.sleep(_human_delay_for_char(ch, h))
        return

    # ДЕТЕРМИНИРОВАННЫЙ РЕЖИМ
    if backend == "win_unicode":
        send_unicode_text(text, per_char_delay=base_delay or 0.0)
    elif backend == "pyautogui":
        for ch in text:
            pag.write(ch)
            if base_delay:
                time.sleep(base_delay)
    else:
        prev = None
        try:
            try:
                prev = pyperclip.paste()
            except Exception:
                prev = None
            pyperclip.copy(text)
            pag.hotkey("ctrl", "v")
        finally:
            if prev is not None:
                try:
                    pyperclip.copy(prev)
                except Exception:
                    pass


@register("press_key")
def press_key(ctx: Context, step: Dict[str, Any]) -> None:
    key = step.get("key")
    hot = step.get("hotkey")
    if (key is None) and (hot is None):
        raise ValueError("press_key: need 'key' or 'hotkey'")

    if ctx.dry_run:
        if hot is not None:
            ctx.console.print(f"[cyan]DRY[/] hotkey: {list(_keys_list(hot))}")
        else:
            ctx.console.print(f"[cyan]DRY[/] key: {key}")
        return

    pag.FAILSAFE = False
    if hot is not None:
        pag.hotkey(*_keys_list(hot))
    else:
        pag.press(str(key))
