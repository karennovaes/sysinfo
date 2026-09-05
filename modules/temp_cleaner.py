"""Limpeza das pastas temporárias do usuário e do sistema no Windows."""

from __future__ import annotations

import os
import platform
import shutil
from typing import Any


def _empty_stats(path: str) -> dict[str, Any]:
    """Cria o conjunto de estatísticas de uma pasta temporária."""
    return {
        "arquivos_deletados": 0,
        "arquivos_ignorados": 0,
        "espaco_liberado_mb": 0.0,
        "caminho": path,
    }


def _directory_depth(path: str) -> int:
    """Retorna uma profundidade estável para caminhos Windows e POSIX."""
    return path.replace("\\", "/").rstrip("/").count("/")


def _clean_directory(path: str) -> dict[str, Any]:
    """Remove o conteúdo de ``path`` e retorna as estatísticas da operação.

    Os arquivos são tentados primeiro. Em seguida, as pastas descobertas são
    removidas de baixo para cima, de modo que pastas vazias também possam ser
    eliminadas. Qualquer falha de acesso ou de remoção é isolada e não impede a
    limpeza do restante da pasta.
    """
    stats = _empty_stats(path)
    if not path or not os.path.isdir(path):
        return stats

    files: list[str] = []
    directories: list[str] = []
    walk_errors: list[OSError] = []

    def on_walk_error(error: OSError) -> None:
        """Registra uma subpasta que não pôde ser percorrida."""
        walk_errors.append(error)

    try:
        for root, dirnames, filenames in os.walk(
            path, topdown=True, onerror=on_walk_error
        ):
            directories.extend(os.path.join(root, name) for name in dirnames)
            files.extend(os.path.join(root, name) for name in filenames)
    except OSError:
        # Uma alteração concorrente ou uma falha ao iniciar a enumeração não
        # deve interromper a limpeza das outras pastas temporárias.
        stats["arquivos_ignorados"] += 1
        return stats

    stats["arquivos_ignorados"] += len(walk_errors)

    for file_path in files:
        size = 0
        try:
            size = os.path.getsize(file_path)
        except OSError:
            # Ainda tentamos remover: o arquivo pode ter desaparecido ou ter
            # mudado entre a enumeração e a leitura do tamanho.
            size = 0

        try:
            os.remove(file_path)
        except OSError:
            stats["arquivos_ignorados"] += 1
            continue

        stats["arquivos_deletados"] += 1
        stats["espaco_liberado_mb"] += size / (1024 * 1024)

    directories.sort(key=_directory_depth, reverse=True)
    for directory in directories:
        if not os.path.isdir(directory):
            # Um diretório pai removido anteriormente também remove seus
            # filhos; isso não é uma falha a ser contabilizada.
            continue
        try:
            shutil.rmtree(directory)
        except OSError:
            # Pastas que ainda contêm arquivos em uso, ou sem permissão, são
            # deixadas no lugar para não interromper as demais remoções.
            stats["arquivos_ignorados"] += 1

    stats["espaco_liberado_mb"] = round(stats["espaco_liberado_mb"], 2)
    return stats


def clean_temp() -> dict[str, Any]:
    """Limpa temporários e o cache do Anota AI e retorna estatísticas."""
    user_path = os.environ.get("TEMP", "")
    system_path = r"C:\Windows\Temp"
    appdata_path = os.environ.get("APPDATA", "")
    anota_cache_path = os.path.join(appdata_path, "anotairesponde")

    result = {
        "temp_user": _empty_stats(user_path),
        "temp_system": _empty_stats(system_path),
        "cache_anota": _empty_stats(anota_cache_path),
        "total_deletado": 0,
        "total_ignorados": 0,
        "total_liberado_mb": 0.0,
    }

    if platform.system() != "Windows":
        return result

    result["temp_user"] = _clean_directory(user_path)
    result["temp_system"] = _clean_directory(system_path)
    result["cache_anota"] = _clean_directory(anota_cache_path)
    folders = (
        result["temp_user"],
        result["temp_system"],
        result["cache_anota"],
    )
    result["total_deletado"] = sum(
        folder["arquivos_deletados"] for folder in folders
    )
    result["total_ignorados"] = sum(
        folder["arquivos_ignorados"] for folder in folders
    )
    result["total_liberado_mb"] = round(
        sum(folder["espaco_liberado_mb"] for folder in folders),
        2,
    )
    return result


def display_temp_cleaner() -> None:
    """Exibe em português o resultado da limpeza dos temporários."""
    if platform.system() != "Windows":
        print("Limpeza de temporários disponível apenas no Windows")
        return

    result = clean_temp()
    user = result["temp_user"]
    system = result["temp_system"]
    anota_cache = result["cache_anota"]

    print("--- LIMPEZA DE ARQUIVOS TEMPORÁRIOS ---")
    print(f"Pasta Temp do usuário: {user['caminho']}")
    print()
    print(f"Pasta Temp do sistema: {system['caminho']}")
    print()
    print(f"Cache do Anota AI: {anota_cache['caminho']}")
    if os.path.isdir(anota_cache["caminho"]):
        print(f"  Arquivos deletados: {anota_cache['arquivos_deletados']}")
        print(
            f"  Arquivos ignorados (em uso): "
            f"{anota_cache['arquivos_ignorados']}"
        )
        print(f"  Espaço liberado: {anota_cache['espaco_liberado_mb']:.2f} MB")
    else:
        print("  Pasta não encontrada (não há cache para limpar)")
    print()
    print(f"Total de arquivos deletados: {result['total_deletado']}")
    print(f"Total de arquivos ignorados: {result['total_ignorados']}")
    print(f"Total de espaço liberado: {result['total_liberado_mb']:.2f} MB")
