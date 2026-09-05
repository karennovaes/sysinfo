"""Verificação dos requisitos mínimos de compatibilidade com o Anota AI."""

from __future__ import annotations

import os
import platform
import re
import subprocess
from typing import Any, Callable

import psutil

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

RunCommand = Callable[..., subprocess.CompletedProcess[str]]


def _processor_name() -> str:
    """Retorna o nome do processador usando as informações disponíveis."""
    name = platform.processor() or ""
    if not name:
        try:
            name = platform.uname().processor or ""
        except (AttributeError, OSError):
            name = ""
    return name.strip() or "Não identificado"


def _check_processor() -> dict[str, Any]:
    """Verifica Intel Core i5/i7/i9 ou AMD Ryzen 5/7/9."""
    name = _processor_name()
    compatible = bool(
        re.search(r"\bi[579](?:\b|[-_])", name, flags=re.IGNORECASE)
        or re.search(r"\bryzen\s*[579](?:\b|[-_])", name, flags=re.IGNORECASE)
    )
    return {
        "nome": name,
        "atende": compatible,
        "mensagem": (
            "Atende — processador compatível"
            if compatible
            else "Não atende — necessário Intel Core i5 ou AMD Ryzen 5 (ou superior)"
        ),
    }


def _check_memory() -> dict[str, Any]:
    """Verifica a memória RAM instalada, considerando 12 GB como ideal."""
    total_gb = psutil.virtual_memory().total / (1024**3)
    if total_gb >= 12:
        message = "Atende (ideal)"
        compatible = True
    elif total_gb >= 8:
        message = "Atende (mínimo)"
        compatible = True
    else:
        message = "Não atende — mínimo de 8GB (ideal: 12GB)"
        compatible = False
    return {"total_gb": total_gb, "atende": compatible, "mensagem": message}


def _parse_storage_type(output: str) -> str | None:
    """Interpreta a saída de WMIC/PowerShell como SSD, HDD ou desconhecida."""
    normalized = output.upper()
    if re.search(r"\bSSD\b", normalized):
        return "SSD"
    if re.search(r"\bHDD\b", normalized) or "HARD DISK" in normalized:
        return "HDD"
    return None


def _detect_storage_type(run_command: RunCommand = subprocess.run) -> str | None:
    """Tenta identificar o tipo do disco principal no Windows."""
    if platform.system() != "Windows":
        return None

    commands = (
        ["wmic", "diskdrive", "get", "mediatype"],
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-PhysicalDisk | Select-Object -ExpandProperty MediaType",
        ],
    )
    for command in commands:
        try:
            result = run_command(
                command,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        output = "\n".join(
            part for part in (result.stdout or "", result.stderr or "") if part
        )
        detected = _parse_storage_type(output)
        if detected:
            return detected
    return None


def _primary_disk_usage() -> psutil._common.sdiskusage:
    """Obtém o tamanho da unidade principal do sistema."""
    if platform.system() == "Windows":
        disk_path = os.environ.get("SystemDrive", "C:") + "\\"
    else:
        disk_path = "/"
    return psutil.disk_usage(disk_path)


def _check_storage() -> dict[str, Any]:
    """Verifica SSD e capacidade da unidade principal."""
    disk = _primary_disk_usage()
    total_gb = disk.total / (1024**3)
    storage_type = _detect_storage_type()

    if storage_type == "SSD" and total_gb >= 120:
        message = "Atende"
        compatible = True
    elif storage_type == "SSD":
        message = "Não atende — SSD com espaço insuficiente"
        compatible = False
    elif storage_type == "HDD":
        message = "Não atende — recomendado SSD"
        compatible = False
    else:
        message = "Não foi possível verificar o tipo de armazenamento"
        compatible = False

    return {
        "tipo": storage_type or "Não identificado",
        "total_gb": total_gb,
        "atende": compatible,
        "mensagem": message,
    }


def _is_64_bit() -> bool:
    """Verifica se o Python/SO em execução é de 64 bits."""
    machine = (platform.machine() or "").lower()
    if "64" in machine:
        return True
    try:
        architecture = platform.architecture()[0].lower()
    except (OSError, IndexError):
        architecture = ""
    return "64" in architecture or (os.name == "nt" and os.sys.maxsize > 2**32)


def _check_operating_system() -> dict[str, Any]:
    """Verifica Windows 10/11 em arquitetura de 64 bits."""
    system = platform.system() or "Desconhecido"
    release = platform.release() or "Desconhecida"
    is_64_bit = _is_64_bit()
    compatible_windows = system == "Windows" and release in {"10", "11"}
    compatible = compatible_windows and is_64_bit

    if compatible:
        message = "Atende"
    elif compatible_windows and not is_64_bit:
        message = "Não atende — necessário 64 bits"
    elif system == "Windows":
        message = "Não atende — necessário Windows 10 Pro 64 bits ou Windows 11"
    else:
        message = "Não atende — necessário Windows 10 Pro 64 bits ou Windows 11"

    return {
        "sistema": system,
        "versao": release,
        "arquitetura_64_bits": is_64_bit,
        "atende": compatible,
        "mensagem": message,
    }


def check_compatibility() -> dict[str, dict[str, Any]]:
    """Coleta e verifica cada requisito mínimo do Anota AI."""
    return {
        "processador": _check_processor(),
        "memoria": _check_memory(),
        "armazenamento": _check_storage(),
        "sistema_operacional": _check_operating_system(),
    }


def _colored(message: str, compatible: bool) -> str:
    """Aplica a cor ANSI correspondente ao resultado da verificação."""
    color = GREEN if compatible else RED
    return f"{color}{message}{RESET}"


def display_compatibility_check() -> None:
    """Exibe os resultados da verificação com mensagens coloridas."""
    if platform.system() == "Windows":
        # Ativa o processamento de sequências ANSI em terminais Windows.
        os.system("")

    results = check_compatibility()
    processor = results["processador"]
    memory = results["memoria"]
    storage = results["armazenamento"]
    operating_system = results["sistema_operacional"]

    print("VERIFICAÇÃO DE COMPATIBILIDADE — ANOTA AI")
    print()
    print(f"Processador: {processor['nome']}")
    print(f"  {_colored(processor['mensagem'], processor['atende'])}")
    print()
    print(f"Memória RAM: {memory['total_gb']:.2f} GB")
    print(f"  {_colored(memory['mensagem'], memory['atende'])}")
    print()
    print(
        f"Armazenamento: {storage['tipo']}, "
        f"{storage['total_gb']:.2f} GB"
    )
    print(f"  {_colored(storage['mensagem'], storage['atende'])}")
    print()
    architecture = "64 bits" if operating_system["arquitetura_64_bits"] else "32 bits"
    print(
        "Sistema Operacional: "
        f"{operating_system['sistema']} {operating_system['versao']} {architecture}"
    )
    print(f"  {_colored(operating_system['mensagem'], operating_system['atende'])}")
