"""Verificação dos requisitos mínimos de compatibilidade com o Anota AI."""

from __future__ import annotations

import csv
import io
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
    name = ""
    if platform.system() == "Windows":
        commands = (
            ["wmic", "cpu", "get", "name"],
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                (
                    "Get-CimInstance Win32_Processor | "
                    "Select-Object -ExpandProperty Name"
                ),
            ],
        )
        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError):
                continue
            for line in (result.stdout or "").splitlines():
                candidate = line.strip()
                if candidate and candidate.lower() != "name":
                    name = candidate
                    break
            if name:
                break

    if not name:
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
        or re.search(r"\bryzen\s*[579]\b", name, flags=re.IGNORECASE)
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
    if (
        re.search(r"\bSSD\b", normalized)
        or "SOLID STATE" in normalized
        or re.search(r"\bNVME\b", normalized)
    ):
        return "SSD"
    if (
        re.search(r"\bHDD\b", normalized)
        or "HARD DISK" in normalized
        or "ROTATIONAL" in normalized
    ):
        return "HDD"
    return None


def _size_to_gb(value: str) -> float | None:
    """Converte um tamanho em bytes (ou com unidade) para GB."""
    match = re.search(
        r"([0-9]+(?:[.,][0-9]+)?)\s*(TB|GB|MB|B)?\s*$",
        value.strip(),
        re.IGNORECASE,
    )
    if not match:
        return None
    try:
        amount = float(match.group(1).replace(",", "."))
    except ValueError:
        return None
    unit = (match.group(2) or "B").upper()
    multipliers = {"B": 1 / (1024**3), "MB": 1 / 1024, "GB": 1, "TB": 1024}
    return amount * multipliers[unit]


def _disk_record(name: str, media_type: str, size: str) -> dict[str, Any] | None:
    """Cria um registro normalizado de disco a partir dos campos encontrados."""
    total_gb = _size_to_gb(size)
    if total_gb is None or total_gb <= 0:
        return None
    detected_type = _parse_storage_type(media_type) or _parse_storage_type(name)
    return {
        "nome": name.strip() or "Não identificado",
        "tipo": detected_type or "Desconhecido",
        "total_gb": total_gb,
    }


def _parse_disk_records(output: str) -> list[dict[str, Any]]:
    """Extrai discos da saída tabular de WMIC ou PowerShell."""
    records: list[dict[str, Any]] = []
    lines = [line.strip() for line in output.splitlines() if line.strip()]

    # Também aceita CSV, útil quando o PowerShell for configurado para uma
    # saída sem ambiguidade entre o nome e o tipo do disco.
    try:
        csv_rows = list(csv.reader(io.StringIO(output)))
    except csv.Error:
        csv_rows = []
    for header_index, row in enumerate(csv_rows):
        normalized_header = [column.strip().lower() for column in row]
        if not {"size", "mediatype"}.issubset(normalized_header):
            continue
        indexes = {
            column: normalized_header.index(column) for column in normalized_header
        }
        for values in csv_rows[header_index + 1 :]:
            if len(values) <= max(indexes.values()):
                continue
            name = values[indexes.get("friendlyname", indexes.get("model", 0))]
            media_type = values[indexes["mediatype"]]
            record = _disk_record(name, media_type, values[indexes["size"]])
            if record:
                records.append(record)
        if records:
            return records

    # Em algumas versões do WMIC, Size não é a última coluna. Identifique o
    # maior número da linha (o tamanho em bytes) ou o valor com unidade, e use
    # o restante para identificar o modelo e o tipo, que podem conter espaços.
    for line in lines:
        is_header = re.search(
            r"\b(model|friendlyname|mediatype|size)\b",
            line,
            re.IGNORECASE,
        ) and not re.search(r"\d", line)
        if is_header:
            continue
        candidates = list(
            re.finditer(
                r"(?<!\w)([0-9]+(?:[.,][0-9]+)?)\s*(TB|GB|MB|B)?(?!\w)",
                line,
                re.IGNORECASE,
            )
        )
        valid_sizes = []
        for candidate in candidates:
            value = candidate.group(0)
            number = _size_to_gb(value)
            has_unit = candidate.group(2) is not None
            if number is not None and (has_unit or number >= 0.1):
                valid_sizes.append((number, candidate))
        if not valid_sizes:
            continue
        _, size_match = max(valid_sizes, key=lambda item: item[0])
        raw_prefix = (
            line[: size_match.start()] + " " + line[size_match.end() :]
        ).strip()
        name = re.sub(
            r"(?:fixed|removable)\s+hard\s+disk\s+media",
            "",
            raw_prefix,
            flags=re.IGNORECASE,
        )
        name = re.sub(
            r"\b(?:SSD|HDD|NVME|SOLID\s+STATE|ROTATIONAL)\b",
            "",
            name,
            flags=re.IGNORECASE,
        )
        name = re.sub(r"\s{2,}", " ", name).strip()
        # O WMIC chama qualquer disco físico de “Fixed hard disk media”;
        # use o modelo para não classificar esse rótulo genérico como HDD.
        record = _disk_record(name, raw_prefix, size_match.group(0))
        if record:
            records.append(record)
    return records


def _list_physical_disks() -> list[dict[str, Any]]:
    """Lista todos os discos físicos no Windows usando WMIC ou PowerShell."""
    if platform.system() != "Windows":
        return []

    commands = (
        ["wmic", "diskdrive", "get", "model,size,mediatype"],
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-PhysicalDisk | Select-Object FriendlyName,MediaType,Size",
        ],
    )
    parsed_disks: list[dict[str, Any]] = []
    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        disks = _parse_disk_records(result.stdout or "")
        if not disks:
            continue
        if any(disk["tipo"] in {"SSD", "HDD"} for disk in disks):
            return disks
        # WMIC can report only “Fixed hard disk media”, which is not enough
        # to distinguish SSD from HDD. Preserve its sizes as a final fallback
        # while allowing PowerShell to provide the more precise MediaType.
        parsed_disks = disks
    return parsed_disks


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
    """Verifica discos físicos no Windows e a unidade principal nos demais sistemas."""
    if platform.system() == "Windows":
        disks = _list_physical_disks()
        qualifying_disk = next(
            (
                disk
                for disk in disks
                if disk["tipo"] == "SSD" and disk["total_gb"] >= 120
            ),
            None,
        )
        if qualifying_disk:
            message = (
                f"Atende — SSD de {qualifying_disk['total_gb']:.2f} GB encontrado"
            )
            compatible = True
        elif disks:
            message = "Não atende — nenhum SSD de 120GB+ encontrado"
            compatible = False
        else:
            message = "Não foi possível verificar"
            compatible = False

        representative = qualifying_disk or (disks[0] if disks else None)
        return {
            "tipo": representative["tipo"] if representative else "Não identificado",
            "total_gb": representative["total_gb"] if representative else 0,
            "discos": disks,
            "atende": compatible,
            "mensagem": message,
        }

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
    """Exibe um resumo compacto e sem códigos ANSI para copiar no chat."""
    results = check_compatibility()
    processor = results["processador"]
    memory = results["memoria"]
    storage = results["armazenamento"]
    operating_system = results["sistema_operacional"]

    def status_line(compatible: bool, message: str = "") -> str:
        """Retorna somente o status essencial, preservando o detalhe da RAM."""
        if compatible and message.startswith("Atende ("):
            return message
        return "Atende" if compatible else "Não atende"

    def format_gb(value: Any) -> str:
        """Formata GB sem casas quando o valor é inteiro."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{number:.0f}" if number.is_integer() else f"{number:.2f}"

    print("Compatibilidade Anota AI:")
    print(
        f"{'✅' if processor['atende'] else '❌'} Processador: "
        f"{processor['nome']} — "
        f"{status_line(processor['atende'], processor['mensagem'])}"
    )
    print(
        f"{'✅' if memory['atende'] else '❌'} RAM: "
        f"{memory['total_gb']:.2f} GB — "
        f"{status_line(memory['atende'], memory['mensagem'])}"
    )
    print(
        f"{'✅' if storage['atende'] else '❌'} {storage['tipo']}: "
        f"{format_gb(storage['total_gb'])} GB — "
        f"{status_line(storage['atende'], storage['mensagem'])}"
    )
    architecture = "64 bits" if operating_system["arquitetura_64_bits"] else "32 bits"
    os_label = (
        f"{operating_system['sistema']} {operating_system['versao']} "
        f"{architecture}"
    )
    print(
        f"{'✅' if operating_system['atende'] else '❌'} SO: {os_label} — "
        f"{status_line(operating_system['atende'], operating_system['mensagem'])}"
    )
