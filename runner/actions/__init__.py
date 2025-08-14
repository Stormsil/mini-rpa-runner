# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Callable, Dict

REGISTRY: Dict[str, Callable] = {}


def register(name: str):
    def deco(func: Callable):
        REGISTRY[name] = func
        return func

    return deco


# важно: импортируем модули, чтобы действия зарегистрировались
from . import run  # noqa: E402,F401
from . import window  # noqa: E402,F401
from . import flow  # noqa: E402,F401
from . import input  # noqa: E402,F401
from . import vision  # noqa: E402,F401
