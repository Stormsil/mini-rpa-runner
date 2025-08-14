# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
from typing import Any, Dict, List, Sequence

from ..utils.timeparse import parse_duration
from ..context import Context
from . import register


def _as_list(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, (list, tuple)):
        return [str(x) for x in val]
    return [str(val)]


@register("run_program")
def run_program(ctx: Context, step: Dict[str, Any]) -> None:
    """
    params:
      path: str (exe)
      args?: list
      cwd?: str
      wait?: bool (по умолчанию False)
      timeout?: duration
    """
    path = step.get("path")
    if not path:
        raise ValueError("run_program: 'path' is required")

    args = _as_list(step.get("args"))
    cwd = step.get("cwd")
    wait = bool(step.get("wait", False))

    timeout = parse_duration(step.get("timeout") or ctx.defaults.get("timeout"))

    cmd: List[str] = [str(path), *args]

    if ctx.dry_run:
        ctx.console.print(
            f"[cyan]DRY[/] run_program: {cmd} (cwd={cwd!r}, wait={wait}, timeout={timeout})"
        )
        return

    proc = subprocess.Popen(
        cmd,
        cwd=cwd or None,
        shell=False,
        creationflags=(
            subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW")
            else 0
        ),
    )

    if wait:
        try:
            rc = proc.wait(timeout=timeout if timeout is not None else None)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise TimeoutError(f"run_program timeout after {timeout}s: {cmd}")
        if rc != 0:
            raise RuntimeError(f"run_program exit code {rc}: {cmd}")


@register("run_ps")
def run_ps(ctx: Context, step: Dict[str, Any]) -> None:
    """
    params:
      script?: str  (путь к .ps1)
      inline?: str  (текст PS-команды)
      args?:  list
      expect_code?: int (default 0)
      timeout?: duration
    """
    script = step.get("script")
    inline = step.get("inline")
    if not script and not inline:
        raise ValueError("run_ps: need 'script' or 'inline'")

    args = _as_list(step.get("args"))
    expect = int(step.get("expect_code", 0))
    timeout = parse_duration(step.get("timeout") or ctx.defaults.get("timeout"))

    if script:
        cmd: Sequence[str] = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *args,
        ]
    else:
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            str(inline),
            *args,
        ]

    if ctx.dry_run:
        ctx.console.print(f"[cyan]DRY[/] run_ps: {cmd} (timeout={timeout})")
        return

    try:
        rc = subprocess.call(cmd, timeout=timeout if timeout is not None else None)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"run_ps timeout after {timeout}s")

    if rc != expect:
        raise RuntimeError(f"run_ps exit code {rc} != expect {expect}")
