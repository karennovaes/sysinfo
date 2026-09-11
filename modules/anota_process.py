"""Diagnóstico, reinício e versão do Anota AI Desktop."""

from __future__ import annotations

import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Iterable

import psutil


def _creation_flags() -> int:
    """Evita uma janela de console quando o aplicativo roda no Windows."""
    return subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0


_EXECUTABLE_NAMES = (
    "anotaai.exe",
    "anota-ai.exe",
    "anotaai-desktop.exe",
    "anota ai.exe",
)


def _normalise_name(value: str) -> str:
    return value.casefold().replace(" ", "").replace("-", "")


def list_anota_processes() -> list[dict[str, str | int]]:
    """Retorna processos cujo nome contém ``anota``."""
    processes: list[dict[str, str | int]] = []
    try:
        iterator = psutil.process_iter(["pid", "name", "status"])
        for process in iterator:
            try:
                info = process.info
                name = str(info.get("name") or "")
                if "anota" not in name.casefold():
                    continue
                status = str(info.get("status") or "unknown")
                state = "running" if status == psutil.STATUS_RUNNING else "not responding"
                processes.append({"pid": info.get("pid", process.pid), "name": name, "status": state})
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except (OSError, RuntimeError):
        return []
    return processes


def display_anota_processes() -> None:
    """Imprime os processos do Anota AI em formato adequado ao terminal."""
    processes = list_anota_processes()
    print("PROCESSOS ATIVOS DO ANOTA AI")
    print("-" * 64)
    if not processes:
        print("O Anota AI Desktop não está rodando.")
        return
    print(f"{'PID':<10} {'NOME':<34} STATUS")
    for item in processes:
        print(f"{item['pid']:<10} {item['name']:<34} {item['status']}")


def _shortcut_targets() -> Iterable[Path]:
    """Obtém destinos de atalhos do Windows sem executar o atalho."""
    if platform.system() != "Windows":
        return []
    roots = [
        Path(os.environ.get("USERPROFILE", "")) / "Desktop",
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    script = (
        "$shell = New-Object -ComObject WScript.Shell; "
        "Get-ChildItem -Path @($args) -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue | "
        "ForEach-Object { $target = $shell.CreateShortcut($_.FullName).TargetPath; "
        "if ($target -and $target -match '(?i)anota') { $target } }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script, *map(str, roots)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            creationflags=_creation_flags(),
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [Path(line.strip()) for line in (result.stdout or "").splitlines() if line.strip()]


def find_anota_executable() -> Path | None:
    """Procura o executável em instalações comuns e em atalhos do Windows."""
    roots: list[Path] = []
    for variable in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "APPDATA"):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value))
    roots.extend(
        Path(path)
        for path in (
            r"C:\Program Files\Anota AI",
            r"C:\Program Files (x86)\Anota AI",
            r"C:\Users\Public\Desktop",
        )
    )

    # Verificações diretas cobrem a maioria das instalações sem varrer o disco.
    for root in roots:
        for name in _EXECUTABLE_NAMES:
            direct = root / name
            if direct.is_file():
                return direct
            nested = root / "anotaai" / name
            if nested.is_file():
                return nested

    for root in roots:
        if not root.is_dir():
            continue
        try:
            for candidate in root.rglob("*.exe"):
                if _normalise_name(candidate.name) in {_normalise_name(name) for name in _EXECUTABLE_NAMES}:
                    return candidate
        except (OSError, PermissionError):
            continue

    for target in _shortcut_targets():
        if target.is_file():
            return target
    return None


def restart_anota() -> str:
    """Encerra processos Anota, aguarda e inicia o executável encontrado."""
    processes = list_anota_processes()
    if platform.system() != "Windows":
        return "Reinício do Anota AI disponível apenas no Windows."
    killed = 0
    for item in processes:
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(item["pid"]), "/F"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
                creationflags=_creation_flags(),
            )
            if result.returncode == 0:
                killed += 1
        except (OSError, subprocess.SubprocessError):
            continue
    time.sleep(2)
    executable = find_anota_executable()
    if executable is None:
        return f"{killed} processo(s) encerrado(s), mas o executável do Anota AI não foi encontrado."
    try:
        subprocess.Popen([str(executable)], creationflags=_creation_flags())
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{killed} processo(s) encerrado(s), mas não foi possível iniciar o Anota AI: {exc}"
    return f"Anota AI reiniciado com sucesso ({killed} processo(s) encerrado(s)).\nExecutável: {executable}"


def installed_version() -> str:
    """Lê a versão do executável usando a metadata do arquivo no Windows."""
    executable = find_anota_executable()
    if executable is None:
        return "Não encontrado"
    if platform.system() != "Windows":
        return f"Executável encontrado: {executable} (versão disponível no Windows)"
    command = (
        "$item = Get-Item -LiteralPath $args[0]; "
        "if ($item.VersionInfo.ProductVersion) { $item.VersionInfo.ProductVersion } "
        "else { 'Não informado' }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command, str(executable)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            creationflags=_creation_flags(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"Executável encontrado: {executable}\nNão foi possível ler a versão: {exc}"
    version = next((line.strip() for line in (result.stdout or "").splitlines() if line.strip()), "Não informado")
    return f"Versão instalada: {version}\nExecutável: {executable}"


def display_restart_anota() -> None:
    print("REINICIAR ANOTA AI")
    print("-" * 64)
    print(restart_anota())


def display_installed_version() -> None:
    print("VERSÃO INSTALADA DO ANOTA AI")
    print("-" * 64)
    print(installed_version())
