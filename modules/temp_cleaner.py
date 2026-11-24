"""Limpeza das pastas temporárias do usuário e do sistema no Windows."""

from __future__ import annotations

import os
import platform
import shutil
from typing import Any, Callable

from modules.security import log_audit

# Pastas dentro do diretório do Anota AI que NÃO devem ser apagadas.
# ``logs`` é usado pelo suporte para diagnóstico; ``config``/``settings``
# guardam preferências do cliente. Só o cache real é removido.
ANOTA_PRESERVED_DIRS = {
    "logs",
    "log",
    "config",
    "configs",
    "settings",
    "data",
    "database",
    "db",
    "backup",
    "backups",
}


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


ProgressCallback = Callable[[int, float], None]
StopCheck = Callable[[], bool]


def _clean_directory(
    path: str,
    on_progress: ProgressCallback | None = None,
    should_stop: StopCheck | None = None,
) -> dict[str, Any]:
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
        if on_progress is not None and stats["arquivos_deletados"] % 100 == 0:
            on_progress(stats["arquivos_deletados"], stats["espaco_liberado_mb"])
        if should_stop is not None and should_stop():
            break

    # Progresso final desta pasta (garante o contador total mesmo se < 100)
    if on_progress is not None:
        on_progress(stats["arquivos_deletados"], stats["espaco_liberado_mb"])

    if should_stop is not None and should_stop():
        stats["espaco_liberado_mb"] = round(stats["espaco_liberado_mb"], 2)
        return stats

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


def _contains_preserved(path: str, preserved_names: set[str]) -> bool:
    """Retorna True se ``path`` contém (em qualquer profundidade) uma subpasta preservada."""
    preserved_lower = {name.casefold() for name in preserved_names}
    for root, dirnames, _ in os.walk(path, topdown=True):
        for name in dirnames:
            if name.casefold() in preserved_lower:
                return True
    return False

def _clean_directory_preserving(
    path: str,
    preserved_names: set[str],
    on_progress: ProgressCallback | None = None,
    should_stop: StopCheck | None = None,
) -> dict[str, Any]:
    """Limpa ``path`` sem tocar nas subpastas listadas em ``preserved_names``.

    Diferente de :func:`_clean_directory`, esta versão percorre a árvore e
    ignora completamente as subpastas preservadas (e todo o seu conteúdo),
    mantendo logs e configurações intactos.
    """
    stats = _empty_stats(path)
    if not path or not os.path.isdir(path):
        return stats

    preserved_lower = {name.casefold() for name in preserved_names}
    files: list[str] = []
    directories: list[str] = []
    walk_errors: list[OSError] = []

    def on_walk_error(error: OSError) -> None:
        walk_errors.append(error)

    try:
        for root, dirnames, filenames in os.walk(
            path, topdown=True, onerror=on_walk_error
        ):
            # Remove da varredura as pastas preservadas, impedindo que o
            # os.walk desça nelas e que sejam adicionadas para remoção.
            dirnames[:] = [
                name for name in dirnames
                if name.casefold() not in preserved_lower
            ]
            directories.extend(os.path.join(root, name) for name in dirnames)
            files.extend(os.path.join(root, name) for name in filenames)
    except OSError:
        stats["arquivos_ignorados"] += 1
        return stats

    stats["arquivos_ignorados"] += len(walk_errors)

    for file_path in files:
        try:
            size = os.path.getsize(file_path)
        except OSError:
            size = 0
        try:
            os.remove(file_path)
        except OSError:
            stats["arquivos_ignorados"] += 1
            continue
        stats["arquivos_deletados"] += 1
        stats["espaco_liberado_mb"] += size / (1024 * 1024)
        if on_progress is not None and stats["arquivos_deletados"] % 100 == 0:
            on_progress(stats["arquivos_deletados"], stats["espaco_liberado_mb"])
        if should_stop is not None and should_stop():
            break

    # Progresso final desta pasta (garante o contador total mesmo se < 100)
    if on_progress is not None:
        on_progress(stats["arquivos_deletados"], stats["espaco_liberado_mb"])

    if should_stop is not None and should_stop():
        stats["espaco_liberado_mb"] = round(stats["espaco_liberado_mb"], 2)
        return stats

    directories.sort(key=_directory_depth, reverse=True)
    for directory in directories:
        if not os.path.isdir(directory):
            continue
        # Segurança extra: nunca remover uma pasta preservada.
        if os.path.basename(directory).casefold() in preserved_lower:
            continue
        # Segurança: nunca remover uma pasta que CONTÉM uma subpasta preservada.
        # shutil.rmtree seria recursivo e apagaria tudo dentro, incluindo logs.
        if _contains_preserved(directory, preserved_names):
            continue
        try:
            shutil.rmtree(directory)
        except OSError:
            stats["arquivos_ignorados"] += 1

    stats["espaco_liberado_mb"] = round(stats["espaco_liberado_mb"], 2)
    return stats


def clean_temp(
    on_progress: ProgressCallback | None = None,
    should_stop: StopCheck | None = None,
) -> dict[str, Any]:
    """Limpa temporários e o cache do Anota AI e retorna estatísticas."""
    user_path = os.environ.get("TEMP", "")
    system_path = r"C:\Windows\Temp"
    appdata_path = os.environ.get("APPDATA", "")
    anota_cache_path = os.path.join(appdata_path, "anotaairesponde")

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

    result["temp_user"] = _clean_directory(user_path, on_progress, should_stop)
    result["temp_system"] = _clean_directory(system_path, on_progress, should_stop)
    result["cache_anota"] = _clean_directory_preserving(
        anota_cache_path, ANOTA_PRESERVED_DIRS, on_progress, should_stop
    )
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


def display_temp_cleaner(
    on_progress: ProgressCallback | None = None,
    should_stop: StopCheck | None = None,
) -> None:
    """Exibe o total da limpeza e um resumo curto por local.

    Se ``on_progress`` for fornecido, é chamado a cada arquivo removido com
    (contador, mb_liberados), permitindo feedback em tempo real na interface.
    """
    # Fase 1: descobrir quantos arquivos existem
    if on_progress is not None:
        on_progress(0, 0.0)

    result = clean_temp(on_progress, should_stop)
    log_audit(
        "temp_clean",
        f"Deletados: {result['total_deletado']}, "
        f"Liberado: {result['total_liberado_mb']:.2f} MB",
    )
    if platform.system() != "Windows":
        print("Limpeza: disponível apenas no Windows")
        return

    user = result["temp_user"]
    system = result["temp_system"]
    anota_cache = result["cache_anota"]

    print(
        f"Limpeza: {result['total_deletado']} arquivos removidos, "
        f"{result['total_liberado_mb']:.1f} MB liberados"
    )
    summary = [
        f"{user['arquivos_deletados']} no Temp usuário",
        f"{system['arquivos_deletados']} no Temp sistema",
    ]
    if os.path.isdir(anota_cache["caminho"]):
        summary.append(
            f"{anota_cache['arquivos_deletados']} no cache Anota AI"
        )
    print(f"({', '.join(summary)})")
    if os.path.isdir(anota_cache["caminho"]):
        preserved = sorted(
            name for name in os.listdir(anota_cache["caminho"])
            if name.casefold() in ANOTA_PRESERVED_DIRS
            and os.path.isdir(os.path.join(anota_cache["caminho"], name))
        )
        if preserved:
            print(f"Preservado no Anota AI: {', '.join(preserved)}")
