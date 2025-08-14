# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import sys


def _is_frozen() -> bool:
    # PyInstaller /cx_Freeze
    return getattr(sys, "frozen", False)


def _app_base_dir(project_root: Path) -> Path:
    # где лежат внешние файлы (scenarios/images) во время работы
    return Path(sys.executable).resolve().parent if _is_frozen() else project_root


def ensure_paths_in_config(
    cfg: Dict[str, Any],
    project_root: Path,
    scenario_path: Path,
    profile_name: str | None,
) -> None:
    """
    Заполняет cfg.paths: project_root, base_dir, scenario_*,
    assets (как в конфиге), assets_abs (полный путь).
    Также добавляет cfg.profile.name для шаблонов Jinja2.
    """
    paths = cfg.setdefault("paths", {})

    base_dir = paths.get("base_dir")
    if not base_dir:
        base_dir = _app_base_dir(project_root)
        paths["base_dir"] = str(base_dir)

    paths.setdefault("project_root", str(project_root))
    paths["scenario_file"] = str(scenario_path)
    paths["scenario_dir"] = str(scenario_path.parent)
    # для сценариев: foo.yaml → foo.assets/
    paths.setdefault(
        "scenario_assets",
        str(scenario_path.parent / (scenario_path.stem + ".assets")),
    )

    # assets: может быть относительным (от base_dir) или абсолютным
    assets_conf = Path(str((paths.get("assets") or "images")))
    assets_abs = (
        assets_conf if assets_conf.is_absolute() else Path(base_dir) / assets_conf
    )
    paths["assets_abs"] = str(assets_abs)

    if profile_name:
        cfg.setdefault("profile", {})["name"] = profile_name


def resolve_image_path(p: str, cfg: Dict[str, Any]) -> Path:
    """
    Резолвит картинку по правилам:
      - абсолютный путь → как есть
      - '@scenario/...'      → В ПАПКЕ assets сценария: <scenario>.assets/
      - '@scenario_dir/...'  → рядом со сценарием (сам каталог scenarios/)
      - '@assets/...'        → внутри глобальной библиотеки изображений (paths.assets_abs)
      - 'foo.png'            → fallback-поиск: <scenario>.assets/ → рядом со сценарием → assets_abs
    """
    p = str(p)
    paths = cfg.get("paths", {})
    scenario_dir = Path(paths.get("scenario_dir", "."))
    scenario_assets = Path(paths.get("scenario_assets", str(scenario_dir)))
    assets_abs = Path(paths.get("assets_abs", "images"))

    q = Path(p)
    if q.is_absolute():
        return q

    if p.startswith("@scenario/"):
        return (scenario_assets / p.split("/", 1)[1]).resolve()

    if p.startswith("@scenario_dir/"):
        return (scenario_dir / p.split("/", 1)[1]).resolve()

    if p.startswith("@assets/"):
        return (assets_abs / p.split("/", 1)[1]).resolve()

    # Fallback порядок поиска:
    cand = scenario_assets / p
    if cand.exists():
        return cand.resolve()

    cand = scenario_dir / p
    if cand.exists():
        return cand.resolve()

    return (assets_abs / p).resolve()
