"""Utilitários de segurança para o Diagnóstico do Sistema.

O módulo concentra as validações usadas pelos downloads e o registro local de
auditoria. Nenhuma dessas operações interrompe a aplicação por uma falha de
escrita do log: a auditoria é complementar e não deve impedir o diagnóstico.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

ALLOWED_DOMAINS = frozenset({"raw.githubusercontent.com", "app.anota.ai"})
HASH_CHUNK_SIZE = 1024 * 1024
AUDIT_LOG_FILENAME = "diagnostico_sysinfo_audit.log"


def validate_url(url: str) -> bool:
    """Valida se ``url`` usa HTTPS e aponta para um domínio confiável.

    A comparação é feita contra o hostname completo, sem aceitar subdomínios,
    URLs com credenciais embutidas ou esquemas alternativos.
    """
    if not isinstance(url, str) or not url:
        return False

    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
    except ValueError:
        return False

    return (
        parsed.scheme.lower() == "https"
        and hostname is not None
        and hostname.lower() in ALLOWED_DOMAINS
        and parsed.username is None
        and parsed.password is None
    )


def calculate_sha256(filepath: str) -> str:
    """Calcula e retorna o SHA-256 de ``filepath`` lendo o arquivo em chunks."""
    digest = hashlib.sha256()
    with open(filepath, "rb") as file_handle:
        while chunk := file_handle.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def verify_hash(filepath: str, expected_hash: str | None = None) -> bool | str:
    """Verifica a integridade de um arquivo via SHA-256.

    Quando ``expected_hash`` é informado, retorna ``True`` se o hash confere e
    ``False`` caso contrário. Sem um hash esperado, retorna o hash calculado,
    permitindo que o chamador o registre ou apresente ao usuário.
    """
    calculated_hash = calculate_sha256(filepath)
    if expected_hash is None:
        return calculated_hash
    return calculated_hash.casefold() == expected_hash.strip().casefold()


def _audit_log_path() -> Path:
    """Retorna o caminho do log no diretório temporário do sistema."""
    return Path(os.environ.get("TEMP") or tempfile.gettempdir()) / AUDIT_LOG_FILENAME


def log_audit(action: str, details: str = "") -> None:
    """Acrescenta uma entrada de auditoria ao log local.

    Falhas de criação ou escrita são deliberadamente ignoradas para que um
    problema no diretório temporário não impeça o uso do aplicativo.
    """
    timestamp = datetime.now().isoformat(timespec="seconds")
    entry = f"[{timestamp}] {action}: {details}\n"
    try:
        with _audit_log_path().open("a", encoding="utf-8") as log_file:
            log_file.write(entry)
    except (OSError, UnicodeError):
        return
