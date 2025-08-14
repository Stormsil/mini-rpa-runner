# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List

import cv2
import numpy as np


@dataclass
class MatchResult:
    rect: Tuple[int, int, int, int]  # x, y, w, h (в координатах сцены/ROI)
    score: float  # 0..1
    method: str  # 'tm'|'edges'|'orb'


# ------------------------------ helpers ------------------------------


def _to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _clahe(g: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    out = clahe.apply(g)
    return cv2.GaussianBlur(out, (3, 3), 0)


def _canny(g: np.ndarray, t1: int, t2: int) -> np.ndarray:
    return cv2.Canny(g, threshold1=int(t1), threshold2=int(t2), L2gradient=True)


def _linspace(lo: float, hi: float, steps: int) -> List[float]:
    if steps <= 1:
        return [float(lo)]
    return list(np.linspace(float(lo), float(hi), int(steps)))


# ---------------------------- template match ----------------------------


def _best_of_tm(
    scene_g: np.ndarray, tmpl_g: np.ndarray
) -> Tuple[float, Tuple[int, int, int, int]]:
    res = cv2.matchTemplate(scene_g, tmpl_g, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    th, tw = tmpl_g.shape[:2]
    x, y = max_loc
    return float(max_val), (x, y, tw, th)


def _search_tm_multiscale(
    scene_g: np.ndarray,
    tmpl_g: np.ndarray,
    scale_range: Tuple[float, float],
    steps: int,
) -> Tuple[float, Tuple[int, int, int, int]]:
    h, w = scene_g.shape[:2]
    best_score = -1.0
    best_rect = (0, 0, 0, 0)
    lo, hi = scale_range
    for s in _linspace(lo, hi, steps):
        if s <= 0:
            continue
        t = (
            tmpl_g
            if abs(s - 1.0) < 1e-3
            else cv2.resize(
                tmpl_g,
                (max(1, int(tmpl_g.shape[1] * s)), max(1, int(tmpl_g.shape[0] * s))),
                interpolation=cv2.INTER_AREA,
            )
        )
        th, tw = t.shape[:2]
        if th == 0 or tw == 0 or th > h or tw > w:
            continue
        score, rect = _best_of_tm(scene_g, t)
        if score > best_score:
            best_score = score
            best_rect = rect
    if best_score < 0:
        return 0.0, (0, 0, 0, 0)
    return best_score, best_rect


# ------------------------------ edges match ------------------------------


def _search_edges_multiscale(
    scene_g: np.ndarray,
    tmpl_g: np.ndarray,
    scale_range: Tuple[float, float],
    steps: int,
    canny: Tuple[int, int],
) -> Tuple[float, Tuple[int, int, int, int]]:
    e_scene = _canny(scene_g, *canny)
    h, w = e_scene.shape[:2]
    e_tmpl_full = _canny(tmpl_g, *canny)

    best_score = -1.0
    best_rect = (0, 0, 0, 0)
    lo, hi = scale_range
    for s in _linspace(lo, hi, steps):
        if s <= 0:
            continue
        e_t = (
            e_tmpl_full
            if abs(s - 1.0) < 1e-3
            else cv2.resize(
                e_tmpl_full,
                (
                    max(1, int(e_tmpl_full.shape[1] * s)),
                    max(1, int(e_tmpl_full.shape[0] * s)),
                ),
                interpolation=cv2.INTER_AREA,
            )
        )
        th, tw = e_t.shape[:2]
        if th == 0 or tw == 0 or th > h or tw > w:
            continue
        res = cv2.matchTemplate(e_scene, e_t, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        x, y = max_loc
        if float(max_val) > best_score:
            best_score = float(max_val)
            best_rect = (x, y, tw, th)
    if best_score < 0:
        return 0.0, (0, 0, 0, 0)
    return best_score, best_rect


# ------------------------------ ORB (features) ------------------------------


def _search_orb(scene_g: np.ndarray, tmpl_g: np.ndarray) -> Optional[MatchResult]:
    # Pylance не знает ORB_create в cv2 — это норм. Игнорим типизацию.
    try:
        orb = cv2.ORB_create(  # type: ignore[attr-defined]
            nfeatures=700, scaleFactor=1.2, nlevels=8, edgeThreshold=15, patchSize=31
        )
    except AttributeError:
        # Старый OpenCV без ORB (редко). Просто откажемся.
        return None

    kp1, des1 = orb.detectAndCompute(tmpl_g, None)
    kp2, des2 = orb.detectAndCompute(scene_g, None)
    if des1 is None or des2 is None or len(kp1) < 6 or len(kp2) < 6:
        return None

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    raw = bf.knnMatch(des1, des2, k=2)

    good = []
    for pair in raw:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < 0.75 * n.distance:
            good.append(m)

    if len(good) < 8:
        return None

    src_pts: np.ndarray = np.asarray(
        [kp1[m.queryIdx].pt for m in good], dtype=np.float32
    ).reshape(-1, 1, 2)
    dst_pts: np.ndarray = np.asarray(
        [kp2[m.trainIdx].pt for m in good], dtype=np.float32
    ).reshape(-1, 1, 2)

    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if H is None or mask is None:
        return None

    inliers = int(mask.ravel().sum())
    h, w = tmpl_g.shape[:2]
    corners: np.ndarray = np.asarray(
        [[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32
    ).reshape(-1, 1, 2)
    proj = cv2.perspectiveTransform(corners, H).reshape(-1, 2)

    x0, y0 = proj.min(axis=0)
    x1, y1 = proj.max(axis=0)
    x, y, ww, hh = int(x0), int(y0), int(x1 - x0), int(y1 - y0)
    if ww <= 0 or hh <= 0:
        return None

    # Нормируем «оценку» по числу инлаеров
    score = max(0.0, min(1.0, inliers / 40.0))
    return MatchResult(rect=(x, y, ww, hh), score=score, method="orb")


# ------------------------------- public API -------------------------------


def find_template(
    scene_bgr: np.ndarray,
    tmpl_bgr: np.ndarray,
    *,
    scale_range: Tuple[float, float] = (0.9, 1.1),
    threshold: float = 0.0,
    steps: int = 9,
    method: str = "auto",  # 'auto'|'tm'|'edges'|'hybrid'|'orb'
    use_clahe: bool = True,
    canny: Optional[Tuple[int, int]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Возвращает { 'rect': (x,y,w,h), 'score': float, 'method': str } или None.
    threshold используется вызывающей стороной.
    """
    # 1) подготовка
    s_g = _to_gray(scene_bgr)
    t_g = _to_gray(tmpl_bgr)
    if use_clahe:
        s_g = _clahe(s_g)
        t_g = _clahe(t_g)

    canny = canny or (80, 180)
    lo, hi = scale_range
    if lo > hi:
        lo, hi = hi, lo
    steps = max(1, int(steps))

    # 2) единичные режимы
    if method == "tm":
        score, rect = _search_tm_multiscale(s_g, t_g, (lo, hi), steps)
        return {"rect": rect, "score": float(score), "method": "tm"}
    if method == "edges":
        score, rect = _search_edges_multiscale(s_g, t_g, (lo, hi), steps, canny=canny)
        return {"rect": rect, "score": float(score), "method": "edges"}
    if method == "orb":
        m = _search_orb(s_g, t_g)
        return (
            None
            if m is None
            else {"rect": m.rect, "score": float(m.score), "method": "orb"}
        )

    # 3) hybrid: берём максимум TM/Edges
    if method == "hybrid":
        score_tm, rect_tm = _search_tm_multiscale(s_g, t_g, (lo, hi), steps)
        score_ed, rect_ed = _search_edges_multiscale(
            s_g, t_g, (lo, hi), steps, canny=canny
        )
        if score_ed >= score_tm:
            return {"rect": rect_ed, "score": float(score_ed), "method": "edges"}
        return {"rect": rect_tm, "score": float(score_tm), "method": "tm"}

    # 4) auto: TM vs Edges → если оба слабы — ORB
    score_tm, rect_tm = _search_tm_multiscale(s_g, t_g, (lo, hi), steps)
    score_ed, rect_ed = _search_edges_multiscale(s_g, t_g, (lo, hi), steps, canny=canny)

    # Небольшая «калибровка»: Edges обычно даёт чуть ниже баллы — поднимем его на чутка
    score_ed_cal = min(1.0, score_ed + 0.04)

    if max(score_tm, score_ed_cal) >= max(threshold, 0.55):
        if score_ed_cal >= score_tm:
            return {"rect": rect_ed, "score": float(score_ed), "method": "edges"}
        return {"rect": rect_tm, "score": float(score_tm), "method": "tm"}

    # Слабо? Пробуем ORB как fallback
    m = _search_orb(s_g, t_g)
    if m is not None:
        return {"rect": m.rect, "score": float(m.score), "method": "orb"}

    # Совсем не нашли
    return None
