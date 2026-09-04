"""Coleta informações de hardware e do sistema operacional."""

from __future__ import annotations

import os
import platform
import socket
from typing import Any

import psutil


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


def collect_system_info() -> dict[str, Any]:
    """Coleta os dados usados pelo diagnóstico."""
    disk_path = os.environ.get("SystemDrive", "C:") + "\\" if os.name == "nt" else "/"
    disk = psutil.disk_usage(disk_path)
    memory = psutil.virtual_memory()
    return {
        "processador": platform.processor() or platform.machine() or "Não identificado",
        "placa_mae": _motherboard_info(),
        "nucleos_fisicos": psutil.cpu_count(logical=False) or 0,
        "nucleos_logicos": psutil.cpu_count(logical=True) or 0,
        "ram_total_gb": memory.total / (1024**3),
        "ram_disponivel_gb": memory.available / (1024**3),
        "windows": _windows_info(),
        "hostname": socket.gethostname(),
        "ip_local": _local_ip(),
        "disco_total_gb": disk.total / (1024**3),
        "disco_usado_gb": disk.used / (1024**3),
        "disco_livre_gb": disk.free / (1024**3),
    }


def display_system_info(info: dict[str, Any] | None = None) -> None:
    """Exibe as informações do sistema em português."""
    info = info or collect_system_info()
    print(f"Processador: {info['processador']}")
    print(f"Placa-mãe: {info['placa_mae']}")
    print(f"Núcleos físicos: {info['nucleos_fisicos']}")
    print(f"Núcleos lógicos: {info['nucleos_logicos']}")
    print(f"RAM total: {info['ram_total_gb']:.2f} GB")
    print(f"RAM disponível: {info['ram_disponivel_gb']:.2f} GB")
    print(f"Windows/SO: {info['windows']}")
    print(f"Nome do computador: {info['hostname']}")
    print(f"IP local: {info['ip_local']}")
    print(
        "Disco: "
        f"{info['disco_usado_gb']:.2f} GB usados de "
        f"{info['disco_total_gb']:.2f} GB "
        f"({info['disco_livre_gb']:.2f} GB livres)"
    )
