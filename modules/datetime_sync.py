"""Exibição de data/hora e sincronização do relógio no Windows."""

from __future__ import annotations

import platform
import re
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

try:
    from tzlocal import get_localzone_name
except ImportError:  # pragma: no cover - usado quando a dependência ainda não foi instalada
    get_localzone_name = None

NTP_SERVER = "time.windows.com"
SYNC_COMMAND = "w32tm /resync"
ENABLE_COMMAND = (
    'sc config w32time start= auto && net start w32time && '
    'w32tm /config /syncfromflags:manual '
    '/manualpeerlist:"time.windows.com,0x9" /update'
)

RunCommand = Callable[..., subprocess.CompletedProcess[str]]


def _local_timezone() -> tuple[str, Any]:
    """Retorna o nome e o objeto do fuso local, com fallback multiplataforma."""
    timezone_name = ""
    if get_localzone_name is not None:
        try:
            timezone_name = get_localzone_name() or ""
        except Exception:
            timezone_name = ""

    local_now = datetime.now().astimezone()
    if not timezone_name:
        timezone_name = getattr(local_now.tzinfo, "key", "") or local_now.tzname() or "Local"

    try:
        local_timezone = ZoneInfo(timezone_name)
    except Exception:
        local_timezone = local_now.tzinfo or timezone.utc
    return timezone_name, local_timezone


def _utc_offset_label(offset: timedelta | None) -> str:
    """Formata um deslocamento como UTC-3 ou UTC+05:30."""
    if offset is None:
        return "UTC (desconhecido)"
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_minutes = abs(total_seconds) // 60
    hours, minutes = divmod(total_minutes, 60)
    if minutes:
        return f"UTC{sign}{hours:02d}:{minutes:02d}"
    return f"UTC{sign}{hours}"


def collect_datetime_info(now: datetime | None = None) -> dict[str, Any]:
    """Coleta data, hora, fuso, offset e estado de horário de verão."""
    timezone_name, local_timezone = _local_timezone()
    current = now.astimezone(local_timezone) if now is not None else datetime.now(local_timezone)
    daylight_saving = current.dst() not in (None, timedelta(0))
    return {
        "date": current.strftime("%d/%m/%Y"),
        "time": current.strftime("%H:%M:%S"),
        "timezone": timezone_name,
        "utc_offset": _utc_offset_label(current.utcoffset()),
        "daylight_saving": daylight_saving,
    }


def _completed_output(result: subprocess.CompletedProcess[str]) -> str:
    """Combina stdout e stderr sem depender do idioma do Windows."""
    return "\n".join(part for part in (result.stdout, result.stderr) if part).strip()


def check_automatic_sync(
    run_command: RunCommand = subprocess.run,
) -> dict[str, str | bool]:
    """Verifica o serviço Windows Time e o modo de sincronização configurado.

    Nenhum comando de alteração é executado. Em sistemas não Windows, a
    funcionalidade é informada como não aplicável, pois o módulo usa o serviço
    nativo Windows Time para sincronização.
    """
    if platform.system() != "Windows":
        return {
            "available": False,
            "enabled": False,
            "status": "não aplicável (disponível apenas no Windows)",
            "command": ENABLE_COMMAND,
        }

    try:
        service = run_command(
            ["sc", "query", "w32time"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        configuration = run_command(
            ["w32tm", "/query", "/configuration"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "available": True,
            "enabled": False,
            "status": f"não foi possível verificar ({exc})",
            "command": ENABLE_COMMAND,
        }

    service_output = _completed_output(service).upper()
    configuration_output = _completed_output(configuration)
    sync_type = re.search(r"(?im)^\s*TYPE\s*:\s*([^\s(]+)", configuration_output)
    service_running = "RUNNING" in service_output
    configured_type = sync_type.group(1).upper() if sync_type else ""
    enabled = service_running and configured_type not in {"NOSYNC", ""}

    if enabled:
        status = "ativada"
    elif service.returncode != 0 or configuration.returncode != 0:
        status = "não foi possível confirmar (consulte o comando abaixo)"
    else:
        status = "desativada"

    return {
        "available": True,
        "enabled": enabled,
        "status": status,
        "command": ENABLE_COMMAND,
    }


def synchronize_ntp(
    run_command: RunCommand = subprocess.run,
) -> dict[str, str | bool]:
    """Solicita ao Windows uma sincronização usando o servidor configurado.

    O comando ``w32tm /resync`` não altera a configuração de peers: ele apenas
    solicita uma nova sincronização ao Windows Time com a configuração atual.
    O servidor público recomendado é exibido para orientar a configuração caso
    o computador ainda não tenha um peer adequado.
    """
    if platform.system() != "Windows":
        return {
            "available": False,
            "success": False,
            "message": "sincronização NTP disponível apenas no Windows",
            "server": NTP_SERVER,
        }

    try:
        result = run_command(
            ["w32tm", "/resync"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "available": True,
            "success": False,
            "message": f"não foi possível executar {SYNC_COMMAND}: {exc}",
            "server": NTP_SERVER,
        }

    output = _completed_output(result)
    if result.returncode == 0:
        message = output or "sincronização solicitada com sucesso"
        return {
            "available": True,
            "success": True,
            "message": message,
            "server": NTP_SERVER,
        }

    message = output or f"o comando terminou com código {result.returncode}"
    return {
        "available": True,
        "success": False,
        "message": f"falha ao sincronizar: {message}",
        "server": NTP_SERVER,
    }


def display_datetime_sync() -> None:
    """Exibe o diagnóstico de data, hora, fuso e sincronização NTP."""
    info = collect_datetime_info()
    print(f"Data atual: {info['date']}")
    print(f"Hora atual: {info['time']}")
    print(f"Fuso horário: {info['timezone']} ({info['utc_offset']})")
    print(
        "Horário de verão: "
        + ("ativo" if info["daylight_saving"] else "inativo/não aplicável")
    )

    automatic = check_automatic_sync()
    print(f"Sincronização automática: {automatic['status']}")
    if not automatic["enabled"]:
        print(f"Comando para ativar/configurar: {automatic['command']}")

    print(f"Sincronização NTP ({NTP_SERVER}): tentando...")
    result = synchronize_ntp()
    print(f"Resultado da sincronização: {result['message']}")
    if not result["success"] and result["available"]:
        print("Verifique se o serviço Windows Time está em execução e se o terminal tem permissões.")
