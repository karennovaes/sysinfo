"""Coleta informações de hardware e do sistema operacional."""

from __future__ import annotations

import os
import platform
import socket
import subprocess
from typing import Any

import psutil


def _processor_name() -> str:
    """Retorna o nome amigável do processador quando disponível."""
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
    return name.strip() or "Não identificado"


def _local_ip() -> str:
    """Obtém o IP local sem enviar dados pela rede."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "Não identificado"
    finally:
        sock.close()


def _windows_info() -> str:
    """Retorna o nome, a versão e o build do sistema operacional."""
    system = platform.system() or "Desconhecido"
    release = platform.release() or "Desconhecida"
    version = platform.version() or "Desconhecida"
    if system == "Windows":
        win_version, _service_pack, build, _extra = platform.win32_ver()
        return (
            f"Windows {release} | versão {win_version or version} | "
            f"build {build or 'Não identificado'}"
        )
    return f"{system} {release} | versão {version} | build não aplicável"


def _motherboard_info() -> str:
    """Obtém fabricante e modelo da placa-mãe quando executado no Windows."""
    if platform.system() != "Windows":
        return "Não identificado (disponível no Windows)"
    try:
        import winreg

        key_path = r"HARDWARE\DESCRIPTION\System\BIOS"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            manufacturer = winreg.QueryValueEx(key, "BaseBoardManufacturer")[0]
            product = winreg.QueryValueEx(key, "BaseBoardProduct")[0]
        return f"{manufacturer} {product}".strip() or "Não identificado"
    except (ImportError, OSError):
        return "Não identificado"


def _disk_record(identifier: str, total_bytes: str | int, free_bytes: str | int) -> dict[str, Any] | None:
    """Normaliza os dados de uma unidade lógica para GB."""
    try:
        total = int(str(total_bytes).strip())
        free = int(str(free_bytes).strip())
    except (TypeError, ValueError):
        return None
    if total <= 0 or free < 0:
        return None

    clean_identifier = identifier.strip().rstrip("\\/") or "Não identificado"
    return {
        "identificador": clean_identifier,
        "letra": clean_identifier,
        "total_gb": total / (1024**3),
        "livre_gb": free / (1024**3),
    }


def _windows_logical_disks() -> list[dict[str, Any]]:
    """Lista todas as unidades lógicas do Windows via WMIC ou psutil."""
    if platform.system() != "Windows":
        return []

    try:
        result = subprocess.run(
            ["wmic", "logicaldisk", "get", "caption,freespace,size"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        result = None

    disks: list[dict[str, Any]] = []
    if result is not None:
        lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
        header_index = next(
            (
                index
                for index, line in enumerate(lines)
                if {"caption", "freespace", "size"}.issubset(
                    {column.lower() for column in line.split()}
                )
            ),
            None,
        )
        if header_index is not None:
            headers = [column.lower() for column in lines[header_index].split()]
            indexes = {column: headers.index(column) for column in ("caption", "freespace", "size")}
            for line in lines[header_index + 1 :]:
                values = line.split()
                if len(values) <= max(indexes.values()):
                    continue
                record = _disk_record(
                    values[indexes["caption"]],
                    values[indexes["size"]],
                    values[indexes["freespace"]],
                )
                if record:
                    disks.append(record)

    if disks:
        return disks

    # WMIC was removed from newer Windows installations. psutil provides the
    # same information without depending on that optional executable.
    try:
        partitions = psutil.disk_partitions(all=False)
    except (OSError, AttributeError):
        partitions = []
    for partition in partitions:
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except OSError:
            continue
        record = _disk_record(partition.device or partition.mountpoint, usage.total, usage.free)
        if record:
            disks.append(record)
    return disks


def _primary_disk_path() -> str:
    """Retorna o caminho da unidade principal para o fallback."""
    if platform.system() == "Windows":
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"


def collect_system_info() -> dict[str, Any]:
    """Coleta os dados usados pelo diagnóstico."""
    logical_disks = _windows_logical_disks()
    if not logical_disks:
        disk_path = _primary_disk_path()
        try:
            disk = psutil.disk_usage(disk_path)
        except OSError:
            # This fallback also keeps mocked Windows environments usable when
            # they do not have a C:\ path available.
            disk = psutil.disk_usage("/")
        logical_disks = [
            {
                "identificador": disk_path.rstrip("\\/") or "/",
                "letra": disk_path.rstrip("\\/") or "/",
                "total_gb": disk.total / (1024**3),
                "livre_gb": disk.free / (1024**3),
            }
        ]

    memory = psutil.virtual_memory()
    primary_disk = logical_disks[0]
    disk_total_gb = primary_disk["total_gb"]
    disk_free_gb = primary_disk["livre_gb"]
    return {
        "processador": _processor_name(),
        "placa_mae": _motherboard_info(),
        "nucleos_fisicos": psutil.cpu_count(logical=False) or 0,
        "nucleos_logicos": psutil.cpu_count(logical=True) or 0,
        "ram_total_gb": memory.total / (1024**3),
        "ram_disponivel_gb": memory.available / (1024**3),
        "windows": _windows_info(),
        "hostname": socket.gethostname(),
        "ip_local": _local_ip(),
        "discos": logical_disks,
        "disco_total_gb": disk_total_gb,
        "disco_usado_gb": disk_total_gb - disk_free_gb,
        "disco_livre_gb": disk_free_gb,
    }


def display_system_info(info: dict[str, Any] | None = None) -> None:
    """Exibe um resumo compacto das informações do sistema."""
    info = info or collect_system_info()

    def format_gb(value: Any) -> str:
        """Formata GB sem casas quando o valor é inteiro."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{number:.0f}" if number.is_integer() else f"{number:.2f}"

    # ``_windows_info`` mantém a versão detalhada para outros consumidores;
    # no relatório, somente o nome do SO e o build são relevantes.
    operating_system_parts = [
        part.strip()
        for part in str(info["windows"]).split("|")
        if "versão" not in part.lower()
    ]
    operating_system = " | ".join(operating_system_parts)

    print("Sistema:")
    print(f"Processador: {info['processador']}")
    print(f"RAM: {info['ram_total_gb']:.2f} GB")
    print(f"SO: {operating_system}")
    print(f"IP: {info['ip_local']}")
    disks = info.get("discos") or []
    if not disks and "disco_total_gb" in info and "disco_livre_gb" in info:
        disks = [
            {
                "identificador": "Disco principal",
                "total_gb": info["disco_total_gb"],
                "livre_gb": info["disco_livre_gb"],
            }
        ]
    for disk in disks:
        identifier = str(disk.get("identificador", disk.get("letra", "Disco")))
        if identifier.lower().startswith("disco "):
            label = identifier
        else:
            label = f"Disco {identifier}"
        if not label.endswith(":"):
            label += ":"
        print(
            f"{label} {format_gb(disk['total_gb'])} GB total, "
            f"{format_gb(disk['livre_gb'])} GB livres"
        )
