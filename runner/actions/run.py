# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..context import Context
from ..utils.timeparse import parse_duration
from . import register


def _resolve_timeout(ctx: Context, step: Dict[str, Any]) -> Optional[float]:
    """
    Цепочка приоритетов:
    1) step.timeout
    2) config.run.timeout
    3) settings.defaults.timeout
    Возвращает seconds | None.
    """
    raw = (
        step.get("timeout")
        or (ctx.config.get("run") or {}).get("timeout")
        or ((ctx.config.get("settings") or {}).get("defaults") or {}).get("timeout")
    )
    return parse_duration(raw)


def _ensure_path(p: str | Path) -> Path:
    q = Path(p)
    if not q.is_absolute():
        q = q.resolve()
    return q


@register("run_program")
def run_program(ctx: Context, step: Dict[str, Any]) -> None:
    """
    params:
      path: str (exe/bat/cmd)
      args?: [str, ...]
      cwd?: str
      wait?: bool (default: false)
      timeout?: duration (используется, если wait=true)
      env?: {k:v} (опционально, поверх текущего env)
    """
    path = step.get("path")
    if not path:
        raise ValueError("run_program: 'path' is required")

    args: List[str] = list(step.get("args") or [])
    cwd_raw = step.get("cwd")
    wait = bool(step.get("wait", False))
    env_add: Dict[str, str] = dict(step.get("env") or {})

    exe = _ensure_path(path)
    if not exe.exists():
        raise FileNotFoundError(f"Executable not found: {exe}")

    cwd = _ensure_path(cwd_raw) if cwd_raw else None
    timeout = _resolve_timeout(ctx, step)

    if ctx.dry_run:
        ctx.console.print(
            f"[cyan]DRY[/] run_program: {exe} args={args} cwd={cwd} wait={wait} timeout={timeout}"
        )
        return

    cmd: List[str] = [str(exe), *args]

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=None if not env_add else {**os.environ, **env_add},
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if wait:
        try:
            out, err = proc.communicate(
                timeout=timeout if timeout is not None else None
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            raise TimeoutError(f"run_program: timeout after {timeout:.1f}s: {exe}")
        if proc.returncode != 0:
            ctx.console.print(f"[red]run_program non-zero exit {proc.returncode}[/]")
            if out:
                ctx.console.print(f"[dim]stdout:[/]\n{out}")
            if err:
                ctx.console.print(f"[dim]stderr:[/]\n{err}")
            raise subprocess.CalledProcessError(proc.returncode, cmd, out, err)
    else:
        ctx.console.print(f"Запущено: {exe.name} (pid={proc.pid})")


@register("run_ps")
def run_ps(ctx: Context, step: Dict[str, Any]) -> None:
    """
    params:
      script?: str (путь к .ps1)  — ИЛИ —
      inline?: str (одной строкой)
      args?: [str, ...]
      wait?: bool (default: true)
      timeout?: duration
      env?: {k:v}
      pwsh?: bool (использовать PowerShell 7, по умолчанию Windows PowerShell)
    """
    script = step.get("script")
    inline = step.get("inline")
    if not script and not inline:
        raise ValueError("run_ps: require 'script' or 'inline'")

    args: List[str] = list(step.get("args") or [])
    wait = bool(step.get("wait", True))
    env_add: Dict[str, str] = dict(step.get("env") or {})
    use_pwsh = bool(step.get("pwsh", False))

    ps_exe = "pwsh.exe" if use_pwsh else "powershell.exe"

    if script:
        ps_script = _ensure_path(script)
        if not ps_script.exists():
            raise FileNotFoundError(f"PowerShell script not found: {ps_script}")
        cmd = [
            ps_exe,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps_script),
            *args,
        ]
    else:
        cmd = [ps_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", inline]

    timeout = _resolve_timeout(ctx, step)

    if ctx.dry_run:
        ctx.console.print(f"[cyan]DRY[/] run_ps: {cmd!r} wait={wait} timeout={timeout}")
        return

    proc = subprocess.Popen(
        cmd,
        shell=False,
        env=None if not env_add else {**os.environ, **env_add},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if wait:
        try:
            out, err = proc.communicate(
                timeout=timeout if timeout is not None else None
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            raise TimeoutError(f"run_ps: timeout after {timeout:.1f}s")
        if proc.returncode != 0:
            ctx.console.print(f"[red]run_ps non-zero exit {proc.returncode}[/]")
            if out:
                ctx.console.print(f"[dim]stdout:[/]\n{out}")
            if err:
                ctx.console.print(f"[dim]stderr:[/]\n{err}")
            raise subprocess.CalledProcessError(proc.returncode, cmd, out, err)
    else:
        ctx.console.print(f"PowerShell запущен (pid={proc.pid})")
