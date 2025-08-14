# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple, cast
import json
import re

import yaml
from jinja2 import Environment, StrictUndefined


# ---------- базовые utils ----------


def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Иммутабельный глубинный мердж: возвращает новый словарь.
    Значения из b перекрывают a.
    """
    out = dict(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


_bool_map = {"true": True, "false": False}


def _parse_scalar(value: str) -> Any:
    """
    Парсит скаляр CLI-оверрайда:
    - true/false -> bool
    - int/float
    - JSON ([], {}, "str") если похоже
    - иначе — строка как есть
    """
    s = value.strip()
    low = s.lower()
    if low in _bool_map:
        return _bool_map[low]
    # число?
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    # JSON?
    if (
        (s.startswith("{") and s.endswith("}"))
        or (s.startswith("[") and s.endswith("]"))
        or (s.startswith('"') and s.endswith('"'))
    ):
        try:
            return json.loads(s)
        except Exception:
            pass
    return s


def parse_overrides(pairs: List[str]) -> Dict[str, Any]:
    """
    Преобразует список вида ["vision.threshold=0.9", "run.timeout=20s"]
    в nested-словарь {"vision":{"threshold":0.9}, "run":{"timeout":"20s"}}
    """
    root: Dict[str, Any] = {}
    for p in pairs:
        if "=" not in p:
            raise ValueError(f"Override must be key=value, got: {p}")
        key, raw = p.split("=", 1)
        keys = key.strip().split(".")
        val = _parse_scalar(raw)
        cur = root
        for k in keys[:-1]:
            nxt = cur.setdefault(k, {})
            if not isinstance(nxt, dict):
                raise ValueError(f"Override path collides at {k} in {p}")
            cur = nxt
        cur[keys[-1]] = val
    return root


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(f"YAML root must be a mapping: {path}")
        return data


def validate_scenario(doc: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if doc.get("version") != 1:
        errors.append("version must be 1")
    steps = doc.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("steps must be a non-empty list")
    else:
        for i, st in enumerate(steps, 1):
            if not isinstance(st, dict):
                errors.append(f"step #{i} must be a mapping")
                continue
            if "action" not in st:
                errors.append(f"step #{i} missing 'action'")
            if "name" not in st:
                errors.append(f"step #{i} missing 'name'")
    return errors


# ---------- загрузка набора конфигов ----------


def resolve_paths(
    project_root: Path,
    scenario: str,
    profile: str | None,
) -> Tuple[Path, Path | None, Path]:
    """
    Возвращает (defaults.yaml, profile.yaml?, scenario.yaml)
    scenario: может быть путём или именем в каталоге scenarios/
    """
    defaults = project_root / "configs" / "defaults.yaml"
    prof = (
        project_root / "configs" / "profiles" / f"{profile}.yaml" if profile else None
    )

    s = Path(scenario)
    if not s.suffix:
        # имя без расширения -> ищем в scenarios/
        s = project_root / "scenarios" / f"{s.name}.yaml"
    if not s.is_absolute():
        s = (project_root / s).resolve()

    return defaults, prof, s


def _render_templates(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Рендерит шаблоны Jinja2 в строковых значениях на основе settings.vars.
    Гарантирует, что на выходе остаётся словарь.
    """
    vars_ = ((cfg.get("settings") or {}).get("vars") or {}).copy()
    env = Environment(undefined=StrictUndefined)

    def _walk(x: Any) -> Any:
        if isinstance(x, str) and "{{" in x:
            return env.from_string(x).render(**vars_)
        if isinstance(x, dict):
            return {k: _walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [_walk(i) for i in x]
        return x

    rendered = _walk(cfg)
    if not isinstance(rendered, dict):
        raise TypeError("Rendered config must be a mapping")
    return cast(Dict[str, Any], rendered)


def load_config(
    project_root: Path,
    scenario: str,
    profile: str | None,
    overrides: List[str],
) -> Dict[str, Any]:
    """
    Загружает defaults → profile → scenario → CLI overrides,
    затем делает рендер шаблонов Jinja2.
    """
    defaults_p, profile_p, scenario_p = resolve_paths(project_root, scenario, profile)

    result: Dict[str, Any] = {}

    if defaults_p.exists():
        result = _deep_merge(result, load_yaml(defaults_p))

    if profile_p and profile_p.exists():
        result = _deep_merge(result, load_yaml(profile_p))

    if not scenario_p.exists():
        raise FileNotFoundError(f"Scenario not found: {scenario_p}")
    scenario_doc = load_yaml(scenario_p)
    result = _deep_merge(result, scenario_doc)

    if overrides:
        result = _deep_merge(result, parse_overrides(overrides))

    # рендер Jinja2-плейсхолдеров после мерджа
    result = _render_templates(result)
    return result
