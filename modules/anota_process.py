"""Diagnóstico, reinício e versão do Anota AI Desktop."""

from __future__ import annotations

import os
import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Iterable

import psutil


def _creation_flags() -> int:
    """Evita uma janela de console quando o aplicativo roda no Windows."""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if platform.system() == "Windows" else 0


_EXECUTABLE_NAMES = (
    "anotaai.exe",
    "anota-ai.exe",
    "anotaai-desktop.exe",
    "anota ai.exe",
)


def _normalise_name(value: str) -> str:
    return value.casefold().replace(" ", "").replace("-", "")


_ANOTA_NAME_MARKERS = ("anota", "anotaai", "anota ai", "anotaresponde")


def _contains_anota_name(value: str) -> bool:
    """Indica se um nome pertence ao conjunto de nomes do Anota AI."""
    normalised = value.casefold()
    return any(marker in normalised for marker in _ANOTA_NAME_MARKERS)


def _scan_roots() -> list[Path]:
    """Monta os diretórios de instalação sem depender de uma unidade fixa."""
    values = [
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("PROGRAMFILES"),
        os.environ.get("LOCALAPPDATA"),
        os.environ.get("APPDATA"),
    ]
    # Em instalações Windows, estas pastas continuam sendo úteis mesmo quando
    # o processo foi iniciado por um usuário com variáveis incompletas.
    values.extend((r"C:\Program Files (x86)", r"C:\Program Files"))
    roots: list[Path] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        root = Path(value)
        key = str(root).casefold()
        if key not in seen:
            roots.append(root)
            seen.add(key)
    return roots


def _read_version(executable: Path) -> str:
    """Obtém a versão do executável usando PowerShell, com fallback para WMIC."""
    if platform.system() != "Windows":
        return "Não disponível neste sistema"

    # O WMIC foi removido de versões recentes do Windows 11. PowerShell usa
    # diretamente os metadados do arquivo e lida melhor com caminhos longos.
    escaped_powershell_path = str(executable).replace("'", "''")
    try:
        result = subprocess.run(
            [
                "powershell",
                "-Command",
                f"(Get-Item '{escaped_powershell_path}').VersionInfo.ProductVersion",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            creationflags=_creation_flags(),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass

    # Fallback para instalações mais antigas do Windows que ainda possuem WMIC.
    escaped_path = str(executable).replace("\\", "\\\\")
    try:
        result = subprocess.run(
            [
                "wmic",
                "datafile",
                "where",
                f"name='{escaped_path}'",
                "get",
                "Version",
                "/value",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            creationflags=_creation_flags(),
        )
    except (OSError, subprocess.SubprocessError):
        pass
    else:
        if result.returncode == 0:
            output = (result.stdout or "") + "\n" + (result.stderr or "")
            match = re.search(r"(?im)^\s*Version\s*=\s*([^\r\n]+)", output)
            if match:
                return match.group(1).strip()
            # Algumas versões do WMIC imprimem cabeçalho e valor em linhas
            # separadas.
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            for index, line in enumerate(lines[:-1]):
                if line.casefold() == "version" and lines[index + 1]:
                    return lines[index + 1]
    return "Versão não encontrada"


def _find_anota_executable(folder: Path) -> Path | None:
    """Retorna um executável dentro de uma pasta identificada como Anota."""
    try:
        candidates = sorted(folder.rglob("*.exe"), key=lambda path: (not _contains_anota_name(path.name), str(path)))
        return candidates[0] if candidates else None
    except (OSError, PermissionError):
        return None


def scan_anota_installation() -> tuple[bool, str, str]:
    """Procura uma instalação do Anota AI em diretórios comuns do Windows.

    O retorno é ``(encontrado, caminho, versão)``. Pastas com nome relacionado
    ao Anota AI também são consideradas instalações; quando há um executável
    dentro delas, o caminho retornado é o executável e sua versão é consultada
    com PowerShell.
    """
    matching_folder: Path | None = None
    for root in _scan_roots():
        if not root.is_dir():
            continue
        try:
            # Aceita também uma raiz que já seja a pasta do aplicativo.
            # Os diretórios abaixo continuam sendo percorridos normalmente.
            if _contains_anota_name(root.name):
                executable = _find_anota_executable(root)
                if executable is not None:
                    return True, str(executable), _read_version(executable)
                matching_folder = root
            for current, directories, files in os.walk(root, topdown=True, followlinks=False):
                current_path = Path(current)
                # Arquivos executáveis têm prioridade porque permitem mostrar a
                # versão real instalada no cartão da interface.
                for filename in files:
                    candidate = current_path / filename
                    if candidate.suffix.casefold() == ".exe" and _contains_anota_name(filename):
                        return True, str(candidate), _read_version(candidate)
                for directory in directories:
                    if _contains_anota_name(directory) and matching_folder is None:
                        folder = current_path / directory
                        executable = _find_anota_executable(folder)
                        if executable is not None:
                            return True, str(executable), _read_version(executable)
                        matching_folder = folder
        except (OSError, PermissionError):
            continue
    if matching_folder is not None:
        return True, str(matching_folder), "Não informado"
    return False, "", ""


_SELF_EXCLUDE_MARKERS = ("diagnostico", "sysinfo", "suporte tools")

def _is_self_process(name: str, pid: int) -> bool:
    """Identifica o próprio utilitário para nao matá-lo acidentalmente."""
    normalised = name.casefold()
    if pid == os.getpid():
        return True
    return any(marker in normalised for marker in _SELF_EXCLUDE_MARKERS)


def list_anota_processes() -> list[dict[str, str | int]]:
    """Retorna processos cujo nome contém ``anota`` (excluindo o próprio utilitário)."""
    processes: list[dict[str, str | int]] = []
    try:
        iterator = psutil.process_iter(["pid", "name", "status"])
        for process in iterator:
            try:
                info = process.info
                name = str(info.get("name") or "")
                if "anota" not in name.casefold():
                    continue
                pid = info.get("pid", process.pid)
                if _is_self_process(name, pid):
                    continue
                status = str(info.get("status") or "unknown")
                state = "running" if status == psutil.STATUS_RUNNING else "not responding"
                processes.append({"pid": pid, "name": name, "status": state})
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except (OSError, RuntimeError):
        return []
    return processes


def kill_anota_processes() -> int:
    """Finaliza processos do Anota AI usando ``taskkill /F /IM``.

    A enumeração continua sendo feita por :func:`list_anota_processes`,
    evitando encerrar processos de outros programas. O comando ``/IM`` é
    executado uma vez para cada nome distinto encontrado; o retorno é a
    quantidade de processos encontrados que o Windows confirmou como
    finalizados.
    """
    if platform.system() != "Windows":
        return 0

    processes = list_anota_processes()
    names: list[str] = []
    process_count_by_name: dict[str, int] = {}
    for process in processes:
        name = str(process.get("name") or "").strip()
        if not name:
            continue
        if _is_self_process(name, int(process.get("pid", 0))):
            continue
        key = name.casefold()
        if key not in process_count_by_name:
            names.append(name)
            process_count_by_name[key] = 0
        process_count_by_name[key] += 1

    killed = 0
    for name in names:
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/IM", name],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
                creationflags=_creation_flags(),
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            killed += process_count_by_name[name.casefold()]
    return killed


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
    """Retorna a versão e o caminho encontrados pelo scanner de instalação."""
    found, path, version = scan_anota_installation()
    if not found:
        return "Não encontrado"
    return f"Versão instalada: {version}\nExecutável ou pasta: {path}"


def display_restart_anota() -> None:
    print("REINICIAR ANOTA AI")
    print("-" * 64)
    print(restart_anota())


def display_installed_version() -> None:
    print("VERSÃO INSTALADA DO ANOTA AI")
    print("-" * 64)
    print(installed_version())
