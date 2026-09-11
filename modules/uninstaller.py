"""Desinstalação completa do Anota AI no Windows.

A rotina é deliberadamente best-effort: um arquivo em uso ou uma chave sem
permissão não impede a limpeza dos demais locais. O relatório final informa
somente os caminhos que foram removidos com sucesso; o caminho retornado pelo
scanner nunca é exibido para o usuário.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Iterable

try:
    from tkinter import messagebox
except ImportError:  # pragma: no cover - Tk pode não existir em ambientes de CI
    messagebox = None  # type: ignore[assignment]

from .anota_process import kill_anota_processes, scan_anota_installation
from .temp_cleaner import clean_temp

_CONFIRMATION = (
    "Tem certeza que deseja desinstalar completamente o Anota AI? "
    "Esta ação não pode ser desfeita."
)
_UNINSTALLER_NAMES = ("uninstall.exe", "unins000.exe")
_GREEN = "\033[92m"
_RESET = "\033[0m"


def _creation_flags() -> int:
    """Impede a abertura de uma janela de console no Windows."""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if platform.system() == "Windows" else 0


def _path_from_env(variable: str, *parts: str) -> Path | None:
    value = os.environ.get(variable)
    if not value:
        return None
    return Path(value).joinpath(*parts)


def _unique_paths(paths: Iterable[Path | None]) -> list[Path]:
    """Remove caminhos repetidos sem normalizar caminhos Windows indevidos."""
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        if path is None:
            continue
        key = os.path.normcase(os.path.normpath(str(path)))
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _installation_folder(scanner_path: str) -> Path | None:
    """Obtém uma pasta de instalação provável a partir do caminho do scanner."""
    if not scanner_path:
        return None
    path = Path(scanner_path)
    current = path.parent if path.suffix.casefold() == ".exe" else path
    # Prefere o primeiro diretório com nome relacionado ao Anota, subindo da
    # pasta encontrada. Isso evita remover uma pasta-pai ampla como Program Files.
    for candidate in (current, *current.parents):
        if "anota" in candidate.name.casefold():
            return candidate
    return current if current.is_dir() else None


def _find_uninstaller(scanner_path: str) -> Path | None:
    """Localiza uninstall.exe ou unins000.exe na instalação escaneada."""
    if not scanner_path:
        return None
    scanned = Path(scanner_path)
    roots = [_installation_folder(scanner_path)]
    if scanned.suffix.casefold() == ".exe":
        roots.append(scanned.parent)
    for root in _unique_paths(roots):
        if not root.is_dir():
            continue
        for name in _UNINSTALLER_NAMES:
            direct = root / name
            if direct.is_file():
                return direct
        try:
            for candidate in root.rglob("*.exe"):
                if candidate.name.casefold() in _UNINSTALLER_NAMES:
                    return candidate
        except (OSError, PermissionError):
            continue
    return None


def _remove_path(path: Path) -> bool:
    """Remove arquivo, link ou diretório e retorna se a remoção ocorreu."""
    try:
        if path.is_symlink() or path.is_file():
            path.unlink()
            return True
        if path.is_dir():
            shutil.rmtree(path)
            return True
    except (OSError, PermissionError):
        return False
    return False


def _remove_paths(paths: Iterable[Path]) -> list[str]:
    removed: list[str] = []
    for path in _unique_paths(paths):
        if _remove_path(path):
            removed.append(str(path))
    return removed


def _installation_paths(scanner_path: str) -> list[Path]:
    """Retorna instalações fixas e, quando seguro, a pasta do scanner."""
    paths: list[Path | None] = [
        _installation_folder(scanner_path),
        Path(r"C:\Program Files (x86)\anotaai"),
        Path(r"C:\Program Files\anotaai"),
        _path_from_env("PROGRAMFILES(X86)", "anotaai"),
        _path_from_env("PROGRAMFILES", "anotaai"),
        _path_from_env("LOCALAPPDATA", "anotaai"),
        _path_from_env("LOCALAPPDATA", "anota ai"),
    ]
    return _unique_paths(paths)


def _application_data_paths() -> list[Path]:
    return _unique_paths(
        [
            _path_from_env("APPDATA", "anotaairesponde"),
            _path_from_env("APPDATA", "anota ai"),
            _path_from_env("LOCALAPPDATA", "anotaairesponde"),
        ]
    )


def _registry_keys() -> tuple[str, ...]:
    return (
        r"HKCU\Software\anotaai",
        r"HKCU\Software\anota ai",
        r"HKCU\Software\anotaairesponde",
        r"HKLM\Software\anotaai",
        r"HKLM\Software\anota ai",
    )


def _remove_registry_keys() -> list[str]:
    removed: list[str] = []
    for key in _registry_keys():
        try:
            result = subprocess.run(
                ["reg", "delete", key, "/f"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
                creationflags=_creation_flags(),
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            removed.append(key)
    return removed


def _shortcut_paths() -> list[Path]:
    paths: list[Path] = []
    desktop = _path_from_env("USERPROFILE", "Desktop")
    paths.extend(
        _unique_paths(
            [
                desktop / "Anota AI.lnk" if desktop else None,
                desktop / "Anota AI Desktop.lnk" if desktop else None,
            ]
        )
    )
    for root in (
        _path_from_env("APPDATA", "Microsoft", "Windows", "Start Menu", "Programs"),
        _path_from_env("PROGRAMDATA", "Microsoft", "Windows", "Start Menu", "Programs"),
    ):
        if root is None or not root.is_dir():
            continue
        try:
            paths.extend(item for item in root.glob("Anota AI*") if item.exists())
        except OSError:
            continue
    return _unique_paths(paths)


def _run_official_uninstaller(scanner_path: str) -> bool:
    uninstaller = _find_uninstaller(scanner_path)
    if uninstaller is None:
        return False
    try:
        # run() aguarda o término do desinstalador oficial antes de continuar.
        subprocess.run(
            [str(uninstaller), "/S"],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            creationflags=_creation_flags(),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def _print_report(
    processes_killed: int,
    official_uninstaller: bool,
    folders_removed: list[str],
    registry_removed: list[str],
    shortcuts_removed: list[str],
    temp_result: dict[str, object],
) -> None:
    """Imprime o relatório final sem expor o caminho detectado pelo scanner."""
    print("\nRELATÓRIO FINAL — DESINSTALAÇÃO DO ANOTA AI")
    print("-" * 64)
    print(f"Processos finalizados: {processes_killed}")
    print(f"Desinstalador executado: {'sim' if official_uninstaller else 'não'}")
    print("Pastas removidas:")
    for path in folders_removed:
        print(f"  - {path}")
    if not folders_removed:
        print("  - nenhuma")
    print("Registro limpo:")
    for key in registry_removed:
        print(f"  - {key}")
    if not registry_removed:
        print("  - nenhuma chave removida (sem permissão ou inexistente)")
    print("Atalhos removidos:")
    for path in shortcuts_removed:
        print(f"  - {path}")
    if not shortcuts_removed:
        print("  - nenhum")
    print(
        "Temporários: "
        f"{temp_result.get('total_deletado', 0)} arquivo(s) removido(s), "
        f"{temp_result.get('total_liberado_mb', 0.0)} MB liberados"
    )
    print(f"{_GREEN}Desinstalação concluída com sucesso!{_RESET}")


def display_uninstall() -> None:
    """Confirma e executa a desinstalação completa do Anota AI."""
    if messagebox is None:
        print("Desinstalação cancelada: tkinter não está disponível.")
        return
    if not messagebox.askyesno("Desinstalar Anota AI", _CONFIRMATION):
        print("Desinstalação cancelada pelo usuário.")
        return

    print("DESINSTALAÇÃO COMPLETA DO ANOTA AI")
    print("[1/8] Finalizando processos do Anota AI...")
    if platform.system() != "Windows":
        print("Disponível apenas no Windows.")
        return
    processes_killed = kill_anota_processes()
    time.sleep(2)
    print(f"Processos finalizados: {processes_killed}")

    print("[2/8] Procurando e executando o desinstalador oficial...")
    found, scanner_path, _version = scan_anota_installation()
    official_uninstaller = _run_official_uninstaller(scanner_path if found else "")
    print(f"Desinstalador executado: {'sim' if official_uninstaller else 'não'}")

    print("[3/8] Removendo pastas de instalação...")
    folders_removed = _remove_paths(_installation_paths(scanner_path if found else ""))
    print(f"Pastas removidas nesta etapa: {len(folders_removed)}")

    print("[4/8] Limpando dados de aplicativo...")
    app_data_removed = _remove_paths(_application_data_paths())
    folders_removed.extend(app_data_removed)
    print(f"Dados de aplicativo removidos: {len(app_data_removed)}")

    print("[5/8] Limpando registro do Windows...")
    registry_removed = _remove_registry_keys()
    print(f"Chaves removidas: {len(registry_removed)}")

    print("[6/8] Removendo atalhos...")
    shortcuts_removed = _remove_paths(_shortcut_paths())
    print(f"Atalhos removidos: {len(shortcuts_removed)}")

    print("[7/8] Limpando arquivos temporários...")
    temp_result = clean_temp()
    print(
        f"Temporários removidos: {temp_result.get('total_deletado', 0)} arquivo(s) "
        f"({temp_result.get('total_liberado_mb', 0.0)} MB)"
    )

    print("[8/8] Gerando relatório final...")
    _print_report(
        processes_killed,
        official_uninstaller,
        folders_removed,
        registry_removed,
        shortcuts_removed,
        temp_result,
    )
