# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

import cv2
import numpy as np
import pyautogui as pag

from ..context import Context
from ..utils.timeparse import parse_duration
from ..vision.grab import grab_bgr
from ..vision.match import find_template
from ..utils.paths import resolve_image_path
from ..utils.win_window import get_client_rect_abs, get_foreground_hwnd
from . import register


def _resolve_region(spec: Any, ctx: Context) -> Tuple[int, int, int, int]:
    cfg = ctx.config
    if spec in (None, "default"):
        spec = (cfg.get("vision") or {}).get("default_region", "screen")

    if spec == "screen":
        import mss

        with mss.mss() as sct:
            mon = sct.monitors[0]
            return mon["left"], mon["top"], mon["width"], mon["height"]

    if spec == "window":
        hwnd = ctx.state.get("target_hwnd") or get_foreground_hwnd()
        if not hwnd:
            raise RuntimeError("region: window → нет активного окна")
        return get_client_rect_abs(hwnd)

    if isinstance(spec, dict):
        return (
            int(spec["left"]),
            int(spec["top"]),
            int(spec["width"]),
            int(spec["height"]),
        )
    raise ValueError(f"Unknown region spec: {spec!r}")


def _load_template(ctx: Context, path: str) -> np.ndarray:
    full = resolve_image_path(path, ctx.config)
    img = cv2.imread(str(full), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Template not found or unreadable: {full}")
    return img


def _normalize_scale_range(raw: Any, cfg: Dict[str, Any]) -> Tuple[float, float]:
    sr = raw or (cfg.get("vision") or {}).get("scale_range") or [0.9, 1.1]
    if isinstance(sr, (list, tuple)) and len(sr) == 2:
        a = float(sr[0])
        b = float(sr[1])
        lo, hi = (a, b) if a <= b else (b, a)
        if lo <= 0 or hi <= 0:
            lo, hi = 1.0, 1.0
        return (lo, hi)
    raise ValueError("scale_range must be a pair like [lo, hi]")


def _matcher_from(
    step: Dict[str, Any], cfg: Dict[str, Any]
) -> Tuple[str, Tuple[int, int], bool]:
    vcfg = cfg.get("vision") or {}
    method = (step.get("matcher") or vcfg.get("matcher") or "hybrid").lower()
    edge_cfg = step.get("edge") or vcfg.get("edge") or {}
    canny = edge_cfg.get("canny") or [80, 180]
    use_clahe = bool(vcfg.get("clahe", True))
    return method, (int(canny[0]), int(canny[1])), use_clahe


def _try_match_with_score(
    ctx: Context,
    region_bbox: Tuple[int, int, int, int],
    tmpl_path: str,
    scale_range: Tuple[float, float],
    steps: int = 9,
    method: str = "hybrid",
    canny: Tuple[int, int] = (80, 180),
    use_clahe: bool = True,
):
    scene = grab_bgr(region_bbox)
    tmpl = _load_template(ctx, tmpl_path)
    best = find_template(
        scene,
        tmpl,
        scale_range=scale_range,
        threshold=0.0,
        steps=steps,
        method=method,
        canny=canny,
        use_clahe=use_clahe,
    )
    score = float(best["score"]) if best else 0.0
    return best, score, scene


def _annotate(
    scene_bgr: np.ndarray, rect: Tuple[int, int, int, int], score: float, method: str
) -> np.ndarray:
    x, y, w, h = rect
    out = scene_bgr.copy()
    cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 255), 2)
    cv2.putText(
        out,
        f"{method}:{score:.3f}",
        (x, max(0, y - 6)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return out


def _artifacts_dir(ctx: Context) -> Path:
    root = Path((ctx.config.get("paths") or {}).get("project_root", "."))
    d = root / "artifacts" / "vision"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _step_stub_name(step: Dict[str, Any]) -> str:
    n = (step.get("name") or step.get("action") or "vision").strip()
    safe = "".join(ch for ch in n if ch.isalnum() or ch in ("-", "_", " "))
    return safe.replace(" ", "_")[:80]


@register("image_exists")
def image_exists(ctx: Context, step: Dict[str, Any]) -> None:
    path = step.get("image")
    if not path:
        raise ValueError("image_exists: 'image' is required")

    region = _resolve_region(step.get("region"), ctx)
    threshold = float(
        step.get("threshold", (ctx.config.get("vision") or {}).get("threshold", 0.87))
    )
    scale_range = _normalize_scale_range(step.get("scale_range"), ctx.config)
    timeout = (
        parse_duration(
            step.get("timeout") or (ctx.config.get("run") or {}).get("timeout")
        )
        or 10.0
    )
    retry_delay = (
        parse_duration(
            step.get("retry_delay")
            or (ctx.config.get("vision") or {}).get("retry_delay")
        )
        or 0.4
    )

    method, canny, use_clahe = _matcher_from(step, ctx.config)

    dbg = step.get("debug") or {}
    show_score = bool(dbg.get("show_score"))
    save_best = bool(dbg.get("save_best"))

    if ctx.dry_run:
        ctx.console.print(
            f"[cyan]DRY[/] image_exists: {path} in {region} thr={threshold} scale={scale_range} matcher={method}"
        )
        return

    left, top, w, h = region
    best_overall = 0.0
    best_rect: Optional[Tuple[int, int, int, int]] = None
    best_method: str = method

    deadline = time.time() + timeout
    while time.time() < deadline:
        hit, score, scene = _try_match_with_score(
            ctx,
            region,
            path,
            scale_range,
            steps=9,
            method=method,
            canny=canny,
            use_clahe=use_clahe,
        )
        if score > best_overall and hit:
            best_overall = score
            best_rect = tuple(hit["rect"])
            best_method = str(hit.get("method", method))
            if save_best:
                annotated = _annotate(scene, best_rect, best_overall, best_method)
                out = _artifacts_dir(ctx) / f"{_step_stub_name(step)}_best.png"
                cv2.imwrite(str(out), annotated)

        if show_score:
            sys.stdout.write(
                f"\r[vision] {method} best={best_overall:.3f} thr={threshold:.2f} region={w}x{h}"
            )
            sys.stdout.flush()

        if hit and score >= threshold:
            if show_score:
                sys.stdout.write("\n")
                sys.stdout.flush()
            ctx.console.print(
                f"Нашёл {path} score={score:.3f} via {hit.get('method', method)}"
            )
            return

        time.sleep(retry_delay)

    if show_score:
        sys.stdout.write("\n")
        sys.stdout.flush()
    raise TimeoutError(
        f"image_exists: not found {path} within {timeout:.1f}s (best={best_overall:.3f}, matcher={method})"
    )


@register("click_image")
def click_image(ctx: Context, step: Dict[str, Any]) -> None:
    path = step.get("image")
    if not path:
        raise ValueError("click_image: 'image' is required")

    region = _resolve_region(step.get("region"), ctx)
    threshold = float(
        step.get("threshold", (ctx.config.get("vision") or {}).get("threshold", 0.87))
    )
    scale_range = _normalize_scale_range(step.get("scale_range"), ctx.config)
    timeout = (
        parse_duration(
            step.get("timeout") or (ctx.config.get("run") or {}).get("timeout")
        )
        or 10.0
    )
    retry_delay = (
        parse_duration(
            step.get("retry_delay")
            or (ctx.config.get("vision") or {}).get("retry_delay")
        )
        or 0.4
    )
    move_duration = parse_duration(step.get("move_duration")) or 0.0
    offset = step.get("offset") or [0, 0]

    method, canny, use_clahe = _matcher_from(step, ctx.config)

    dbg = step.get("debug") or {}
    show_score = bool(dbg.get("show_score"))
    save_best = bool(dbg.get("save_best"))

    if ctx.dry_run:
        ctx.console.print(
            f"[cyan]DRY[/] click_image: {path} in {region} thr={threshold} scale={scale_range} matcher={method} "
            f"move={move_duration}s offset={offset}"
        )
        return

    left, top, w, h = region
    best_overall = 0.0
    best_rect: Optional[Tuple[int, int, int, int]] = None
    best_method: str = method

    deadline = time.time() + timeout
    while time.time() < deadline:
        hit, score, scene = _try_match_with_score(
            ctx,
            region,
            path,
            scale_range,
            steps=9,
            method=method,
            canny=canny,
            use_clahe=use_clahe,
        )

        if score > best_overall and hit:
            best_overall = score
            best_rect = tuple(hit["rect"])
            best_method = str(hit.get("method", method))
            if save_best:
                annotated = _annotate(scene, best_rect, best_overall, best_method)
                out = _artifacts_dir(ctx) / f"{_step_stub_name(step)}_best.png"
                cv2.imwrite(str(out), annotated)

        if show_score:
            sys.stdout.write(
                f"\r[vision] {method} best={best_overall:.3f} thr={threshold:.2f} region={w}x{h}"
            )
            sys.stdout.flush()

        if hit and score >= threshold:
            x, y, tw, th = hit["rect"]
            cx = left + x + tw // 2 + int(offset[0])
            cy = top + y + th // 2 + int(offset[1])
            if show_score:
                sys.stdout.write("\n")
                sys.stdout.flush()
            pag.FAILSAFE = False
            pag.moveTo(cx, cy, duration=move_duration)
            pag.click(cx, cy)
            ctx.console.print(
                f"Клик по {path} @ ({cx},{cy}) score={score:.3f} via {hit.get('method', method)}"
            )
            return

        time.sleep(retry_delay)

    if show_score:
        sys.stdout.write("\n")
        sys.stdout.flush()
    raise TimeoutError(
        f"click_image: not found {path} within {timeout:.1f}s (best={best_overall:.3f}, matcher={method})"
    )
