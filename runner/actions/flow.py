# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple, cast

import cv2
import mss
import numpy as np
import psutil
import pygetwindow as gw

from ..utils.timeparse import parse_duration
from ..context import Context
from . import register, REGISTRY
from ..vision.grab import grab_bgr
from ..vision.match import find_template

PatternStr = re.Pattern[str]

# ===================== helpers =====================


def _re_from_expr(expr: str) -> PatternStr:
    if not isinstance(expr, str):
        raise ValueError("regex expression must be a string")
    flags = 0
    body = expr
    if expr.startswith("/") and expr.endswith("/i"):
        body = expr[1:-2]
        flags = re.I
    elif expr.startswith("/") and expr.endswith("/"):
        body = expr[1:-1]
    return re.compile(body, flags)


def _re_from_optional_expr(expr: Optional[str]) -> Optional[PatternStr]:
    return None if expr is None else _re_from_expr(expr)


def _resolve_region(spec: Any, cfg: Dict[str, Any]) -> Tuple[int, int, int, int]:
    """
    region: None|"default"|"screen"|"window"|{left,top,width,height}
    """
    if spec in (None, "default"):
        spec = (cfg.get("vision") or {}).get("default_region", "screen")

    if spec == "screen":
        with mss.mss() as sct:
            mon = sct.monitors[0]
            return mon["left"], mon["top"], mon["width"], mon["height"]

    if spec == "window":
        from ..utils.win_window import get_active_client_bbox

        return get_active_client_bbox()

    if isinstance(spec, dict):
        return (
            int(spec["left"]),
            int(spec["top"]),
            int(spec["width"]),
            int(spec["height"]),
        )

    raise ValueError(f"Unknown region spec: {spec!r}")


def _load_template(ctx: Context, path: str) -> np.ndarray:
    from ..utils.paths import resolve_image_path

    full = resolve_image_path(path, ctx.config)
    img = cv2.imread(str(full), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Template not found or unreadable: {full}")
    return img


def _scale_range2(val: Any, cfg: Dict[str, Any]) -> Tuple[float, float]:
    src = val if val is not None else (cfg.get("vision") or {}).get("scale_range")
    if isinstance(src, (list, tuple)) and len(src) >= 2:
        return float(src[0]), float(src[1])
    return 0.9, 1.1


def _try_match(
    ctx: Context,
    region_bbox: Tuple[int, int, int, int],
    tmpl_path: str,
    threshold: float,
    scale_range: Tuple[float, float],
    steps: int = 9,
) -> Optional[Dict[str, Any]]:
    scene = grab_bgr(region_bbox)
    tmpl = _load_template(ctx, tmpl_path)
    return find_template(
        scene,
        tmpl,
        scale_range=scale_range,
        threshold=float(threshold),
        steps=steps,
    )


def _run_steps_inline(
    ctx: Context, steps: List[Dict[str, Any]], parent_name: str | None = None
) -> None:
    from time import perf_counter, sleep

    delay_between = (
        parse_duration(
            ((ctx.config.get("settings") or {}).get("defaults") or {}).get(
                "delay_between_steps"
            )
        )
        or 0.0
    )

    for idx, step in enumerate(steps, 1):
        name = step.get("name", f"step #{idx}")
        action = step.get("action")
        if not action:
            raise ValueError(f"Inline step #{idx} '{name}' has no 'action'")

        title = name if not parent_name else f"{parent_name} › {name}"
        ctx.console.rule(f"[bold]Шаг[/] — {title}  ([dim]{action}[/])")

        delay_before = parse_duration(step.get("delay_before"))
        delay_after = parse_duration(step.get("delay_after"))

        announce = step.get("announce")
        if announce:
            ctx.console.print(announce)

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
                ctx.console.print(f"[red]{fail_msg}[/]")
            raise
        dt = perf_counter() - t0

        success = step.get("success")
        if success:
            ctx.console.print(success)

        ctx.console.print(f"[green]OK[/] ({dt:.2f}s)")

        if delay_after:
            sleep(delay_after)

        if delay_between > 0:
            sleep(delay_between)


# ===================== basic actions =====================


@register("log")
def action_log(ctx: Context, step: Dict[str, Any]) -> None:
    msg = str(step.get("message", ""))
    ctx.console.print(msg)


@register("sleep")
def action_sleep(ctx: Context, step: Dict[str, Any]) -> None:
    """
    params:
      duration: 100ms|2s|1m (или число секунд)
    """
    duration = parse_duration(step.get("duration"))
    if duration is None:
        raise ValueError("sleep: 'duration' is required")
    if ctx.dry_run:
        ctx.console.print(f"[cyan]DRY[/] sleep: {duration:.3f}s")
        return
    time.sleep(duration)


@register("pause")
def action_pause(ctx: Context, step: Dict[str, Any]) -> None:
    """
    Пауза сценария. Варианты:
      - message?: текст подсказки
      - timeout?: 5s  (если указан — просто ждём N секунд)
    """
    msg = str(step.get("message") or "Пауза — нажмите Enter для продолжения…")
    timeout = parse_duration(step.get("timeout"))
    if ctx.dry_run:
        ctx.console.print(f"[cyan]DRY[/] pause: {msg}")
        return
    if timeout is not None:
        ctx.console.print(f"{msg} (продолжу через {timeout:.1f}s)")
        time.sleep(timeout)
    else:
        ctx.console.print(msg)
        try:
            input()  # блокирующая пауза в консоли
        except EOFError:
            # если ввода нет (запуск без stdin) — fallback на 3 сек
            time.sleep(3.0)


@register("checkpoint")
def action_checkpoint(ctx: Context, step: Dict[str, Any]) -> None:
    """
    params:
      id: строка идентификатора чекпоинта
    """
    cid = str(step.get("id") or "").strip()
    if not cid:
        raise ValueError("checkpoint: 'id' is required")
    ctx.state[f"checkpoint:{cid}"] = True
    ctx.console.print(f"[green]Checkpoint:[/] {cid}")


# ===================== conditions =====================


def _cond_image_exists(ctx: Context, spec: Dict[str, Any]) -> bool:
    path = spec.get("image")
    if not path:
        raise ValueError("image_exists: 'image' is required")

    region = _resolve_region(spec.get("region"), ctx.config)
    threshold = float(
        spec.get("threshold", (ctx.config.get("vision") or {}).get("threshold", 0.87))
    )
    scale_range = _scale_range2(spec.get("scale_range"), ctx.config)
    timeout = (
        parse_duration(spec.get("timeout"))
        or parse_duration((ctx.config.get("run") or {}).get("timeout"))
        or 10.0
    )
    retry_delay = (
        parse_duration(spec.get("retry_delay"))
        or parse_duration((ctx.config.get("vision") or {}).get("retry_delay"))
        or 0.4
    )

    deadline = time.time() + timeout
    best = 0.0
    while time.time() < deadline:
        hit = _try_match(ctx, region, path, threshold, scale_range)
        if hit:
            return True
        # подсмотрим лучший скор (без порога)
        probe = _try_match(ctx, region, path, 0.0, scale_range)
        if probe:
            best = max(best, float(probe["score"]))
        time.sleep(retry_delay)

    ctx.console.print(f"[dim]image_exists: best={best:.3f} < thr={threshold:.2f}[/dim]")
    return False


def _cond_window_exists(ctx: Context, spec: Dict[str, Any]) -> bool:
    title_rx = _re_from_optional_expr(cast(Optional[str], spec.get("title")))
    class_rx = _re_from_optional_expr(cast(Optional[str], spec.get("class")))

    if title_rx is None and class_rx is None:
        raise ValueError("window_exists: 'title' or 'class' is required")

    for w in gw.getAllWindows():
        # гарантируем именно str
        title: str = cast(str, (getattr(w, "title", "") or ""))

        if title_rx is not None:
            if cast(PatternStr, title_rx).search(title) is None:
                continue

        if class_rx is not None:
            cls = ""
            try:
                import win32gui  # type: ignore

                cls = win32gui.GetClassName(int(w._hWnd))  # noqa: SLF001
            except Exception:
                cls = ""
            cls = cast(str, (cls or ""))
            if cast(PatternStr, class_rx).search(cls) is None:
                continue

        return True

    return False


def _cond_process_exists(ctx: Context, spec: Dict[str, Any]) -> bool:
    pid_obj = spec.get("pid")
    name_expr = cast(Optional[str], spec.get("name"))

    if pid_obj is None and not name_expr:
        raise ValueError("process_exists: 'pid' or 'name' is required")

    if pid_obj is not None:
        try:
            p = psutil.Process(int(pid_obj))
            return p.is_running()
        except Exception:
            return False

    # имя процесса по regex
    assert name_expr is not None
    name_re = _re_from_expr(name_expr)
    for p in psutil.process_iter(["name"]):
        try:
            nm: str = cast(str, (p.info.get("name") or ""))
        except Exception:
            nm = ""
        if name_re.search(nm) is not None:
            return True
    return False


def _eval_condition(ctx: Context, cond: Dict[str, Any]) -> bool:
    kind = (cond.get("type") or "").strip()
    if kind == "image_exists":
        return _cond_image_exists(ctx, cond)
    if kind == "window_exists":
        return _cond_window_exists(ctx, cond)
    if kind == "process_exists":
        return _cond_process_exists(ctx, cond)
    if kind == "attempts_ge":
        cid = str(cond.get("counter_id") or "")
        if not cid:
            raise ValueError("attempts_ge: 'counter_id' is required")
        if "value" not in cond:
            raise ValueError("attempts_ge: 'value' is required")
        limit = int(cast(Any, cond["value"]))
        cur = int(cast(Any, ctx.state.get(f"counter:{cid}", 0)))
        return cur >= limit
    raise ValueError(f"unknown condition type: {kind!r}")


# ===================== flow actions =====================


def _do_if_like(ctx: Context, step: Dict[str, Any]) -> None:
    cond = cast(Dict[str, Any], step.get("condition") or {})
    ok = _eval_condition(ctx, cond)

    branch = "then" if ok else "else"
    substeps: List[Dict[str, Any]] = cast(List[Dict[str, Any]], step.get(branch) or [])
    ctx.console.print(
        f"[cyan]if[/]: {cond.get('type')} → {'[green]TRUE[/]' if ok else '[red]FALSE[/]'} ({len(substeps)} steps)"
    )
    if not substeps:
        return

    _run_steps_inline(ctx, substeps, parent_name=step.get("name") or "if")


@register("if_condition")
def action_if_condition(ctx: Context, step: Dict[str, Any]) -> None:
    _do_if_like(ctx, step)


@register("if")
def action_if(ctx: Context, step: Dict[str, Any]) -> None:
    _do_if_like(ctx, step)


@register("repeat_until")
def action_repeat_until(ctx: Context, step: Dict[str, Any]) -> None:
    """
    Повторяет блок try: пока condition не TRUE или пока не исчерпан max_attempts.
    Поддерживает накопительный счётчик попыток в ctx.state (counter:<id>).
    Ошибки внутри try-шагов не роняют сценарий — логируем и продолжаем.
    """
    tries: List[Dict[str, Any]] = cast(List[Dict[str, Any]], step.get("try") or [])
    if not tries:
        raise ValueError("repeat_until: 'try' steps are required")

    cond: Dict[str, Any] = cast(Dict[str, Any], step.get("condition") or {})
    if not cond:
        raise ValueError("repeat_until: 'condition' is required")

    max_attempts = int(step.get("max_attempts", 1))
    if max_attempts < 1:
        raise ValueError("repeat_until: max_attempts must be >= 1")

    delay_between = parse_duration(step.get("delay_between_attempts"))
    if delay_between is None:
        delay_between = (
            parse_duration(
                ((ctx.config.get("settings") or {}).get("defaults") or {}).get(
                    "retry_delay"
                )
            )
            or 0.5
        )

    cid: str = str(
        step.get("counter_id")
        or (step.get("name") or "repeat").lower().replace(" ", "_")
    )
    attempts: int = int(cast(Any, ctx.state.get(f"counter:{cid}", 0)))

    for attempt in range(1, max_attempts + 1):
        attempts += 1
        ctx.state[f"counter:{cid}"] = attempts
        ctx.console.print(
            f"[dim]repeat_until[/] attempt {attempt}/{max_attempts} (counter_id={cid})"
        )

        # ВАЖНО: try-блок не должен ронять весь repeat
        try:
            _run_steps_inline(ctx, tries, parent_name=step.get("name") or "repeat")
        except Exception as e:
            ctx.console.print(f"[dim]repeat_until: try-block error: {e}[/dim]")

        ok = _eval_condition(ctx, cond)
        if ok:
            ctx.console.print(
                f"[green]repeat_until: success on attempt {attempt}[/green]"
            )
            for sub in cast(List[Dict[str, Any]], step.get("on_success") or []):
                _run_steps_inline(ctx, [sub], parent_name=step.get("name") or "repeat")
            return

        if attempt < max_attempts and delay_between > 0:
            time.sleep(delay_between)

    ctx.console.print(f"[red]repeat_until: failed after {max_attempts} attempts[/red]")
    for sub in cast(List[Dict[str, Any]], step.get("on_fail") or []):
        _run_steps_inline(ctx, [sub], parent_name=step.get("name") or "repeat")
