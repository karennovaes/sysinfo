"""Exibição de data/hora e sincronização do relógio no Windows."""

from __future__ import annotations

import platform
import re
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from modules.security import log_audit

try:
    from tzlocal import get_localzone_name
except ImportError:  # pragma: no cover - usado quando a dependência ainda não foi instalada
    get_localzone_name = None

NTP_SERVER = "a.st1.ntp.br"
NTP_SERVER_FALLBACK = "time.windows.com"
SYNC_COMMAND = "w32tm /resync /rediscover"
ENABLE_COMMAND = (
    'sc config w32time start= auto && net start w32time && '
    'w32tm /config /syncfromflags:manual '
    '/manualpeerlist:"a.st1.ntp.br,0x9 time.windows.com,0x9" /update'
)

RunCommand = Callable[..., subprocess.CompletedProcess[str]]


def _creation_flags() -> int:
    """Evita janelas de console para comandos auxiliares no Windows."""
    creationflags = 0
    if platform.system() == "Windows":
        creationflags = subprocess.CREATE_NO_WINDOW
    return creationflags


def _startup_info() -> "subprocess.STARTUPINFO | None":
    """Configura STARTUPINFO para ocultar a janela do console no Windows."""
    if platform.system() != "Windows":
        return None
    startupinfo_type = getattr(subprocess, "STARTUPINFO", None)
    if startupinfo_type is None:
        return None
    try:
        startupinfo = startupinfo_type()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    except (AttributeError, OSError, TypeError):
        return None
    return startupinfo


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
            creationflags=_creation_flags(),
            startupinfo=_startup_info(),
        )
        configuration = run_command(
            ["w32tm", "/query", "/configuration"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            creationflags=_creation_flags(),
            startupinfo=_startup_info(),
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
    elif service.returncode == 0 and not service_running:
        status = (
            "desativada (serviço Windows Time parado). "
            "Execute como administrador para iniciar o serviço"
        )
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


def _run_hidden(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str] | None:
    """Executa um comando oculto e devolve o resultado, ou None em falha."""
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=_creation_flags(),
            startupinfo=_startup_info(),
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _enable_automatic_time() -> tuple[bool, str]:
    """Ativa 'Definir hora automaticamente' e 'Definir fuso horário automaticamente'."""
    if platform.system() != "Windows":
        return False, "não aplicável (disponível apenas no Windows)"

    # Registro: ativa sincronização automática de hora e de fuso horário.
    # Type=NTP  -> "Definir hora automaticamente"
    # RealTimeIsUniversal / TimeZoneKeyName -> fuso automático
    commands = [
        [
            "reg", "add",
            r"HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Parameters",
            "/v", "Type", "/t", "REG_SZ", "/d", "NTP", "/f",
        ],
        [
            "reg", "add",
            r"HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Parameters",
            "/v", "NtpServer", "/t", "REG_SZ",
            "/d", f"{NTP_SERVER},0x9 {NTP_SERVER_FALLBACK},0x9", "/f",
        ],
        [
            "reg", "add",
            r"HKLM\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpClient",
            "/v", "Enabled", "/t", "REG_DWORD", "/d", "1", "/f",
        ],
        [
            "reg", "add",
            r"HKLM\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpClient",
            "/v", "SpecialPollInterval", "/t", "REG_DWORD", "/d", "3600", "/f",
        ],
    ]

    failures: list[str] = []
    for command in commands:
        result = _run_hidden(command, timeout=15)
        if result is None or result.returncode != 0:
            failures.append(" ".join(command[:4]))

    # Ativa o fuso horário automático via PowerShell (Set-TimeZone com -Auto)
    tz_result = _run_hidden(
        [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "Set-Service -Name tzautoupdate -StartupType Automatic -ErrorAction SilentlyContinue; "
            "Start-Service -Name tzautoupdate -ErrorAction SilentlyContinue; "
            "Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\tzautoupdate' "
            "-Name Start -Value 2 -ErrorAction SilentlyContinue",
        ],
        timeout=30,
    )
    if tz_result is None or tz_result.returncode != 0:
        failures.append("tzautoupdate")

    if failures:
        return False, "falha ao configurar: " + ", ".join(failures)
    return True, "hora e fuso automáticos ativados"


def _set_ntp_server() -> tuple[bool, str]:
    """Troca o servidor de horário para o NTP.br com fallback da Microsoft."""
    if platform.system() != "Windows":
        return False, "não aplicável (disponível apenas no Windows)"

    peers = f"{NTP_SERVER},0x9 {NTP_SERVER_FALLBACK},0x9"
    result = _run_hidden(
        [
            "w32tm", "/config",
            "/syncfromflags:manual",
            f"/manualpeerlist:{peers}",
            "/reliable:yes",
            "/update",
        ],
        timeout=30,
    )
    if result is None:
        return False, "não foi possível executar w32tm /config"
    output = _completed_output(result)
    if result.returncode != 0:
        return False, output or f"w32tm /config terminou com código {result.returncode}"
    return True, f"servidor definido: {NTP_SERVER} (fallback {NTP_SERVER_FALLBACK})"


def synchronize_ntp(
    run_command: RunCommand = subprocess.run,
) -> dict[str, str | bool]:
    """Executa a configuração completa de data/hora e sincroniza o relógio.

    Etapas:
    1. Ativa "Definir hora automaticamente" (serviço w32time + registro)
    2. Ativa "Definir fuso horário automaticamente" (serviço tzautoupdate)
    3. Troca o servidor de horário para a.st1.ntp.br (fallback time.windows.com)
    4. Sincroniza com rediscovery (w32tm /resync /rediscover)
    """
    if platform.system() != "Windows":
        return {
            "available": False,
            "success": False,
            "message": "sincronização NTP disponível apenas no Windows",
            "server": NTP_SERVER,
            "steps": [],
        }

    steps: list[tuple[str, bool, str]] = []

    # --- Etapa 1: serviço Windows Time ativo e automático ---
    service = _run_hidden(["sc", "config", "w32time", "start=", "auto"], timeout=15)
    service_ok = service is not None and service.returncode == 0
    steps.append(("Serviço Windows Time em automático", service_ok,
                  _completed_output(service) if service else "falha ao executar sc config"))

    start = _run_hidden(["net", "start", "w32time"], timeout=30)
    start_ok = start is not None and start.returncode == 0
    # Código 2 costuma significar "já está em execução" — tratamos como sucesso.
    if start is not None and start.returncode == 2:
        start_ok = True
    steps.append(("Serviço Windows Time iniciado", start_ok,
                  _completed_output(start) if start else "falha ao executar net start"))

    # --- Etapa 2: hora e fuso automáticos ---
    auto_ok, auto_msg = _enable_automatic_time()
    steps.append(("Hora e fuso horário automáticos", auto_ok, auto_msg))

    # --- Etapa 3: troca do servidor de horário ---
    server_ok, server_msg = _set_ntp_server()
    steps.append(("Servidor de horário atualizado", server_ok, server_msg))

    # --- Etapa 4: sincronização com rediscovery ---
    resync = _run_hidden(["w32tm", "/resync", "/rediscover"], timeout=30)
    resync_output = _completed_output(resync) if resync else "falha ao executar w32tm /resync"
    resync_ok = resync is not None and resync.returncode == 0
    steps.append(("Sincronização com rediscovery", resync_ok, resync_output))

    # Se o resync falhou, tenta uma vez sem rediscover (compatibilidade)
    if not resync_ok:
        retry = _run_hidden(["w32tm", "/resync"], timeout=30)
        if retry is not None and retry.returncode == 0:
            resync_ok = True
            steps[-1] = ("Sincronização (fallback sem rediscover)", True,
                         _completed_output(retry))

    success = all(ok for _, ok, _ in steps)
    if success:
        message = "data/hora e fuso configurados e sincronizados com sucesso"
    else:
        failed = [name for name, ok, _ in steps if not ok]
        message = (
            "algumas etapas falharam: " + ", ".join(failed) +
            ". Execute o programa como Administrador."
        )

    return {
        "available": True,
        "success": success,
        "message": message,
        "server": NTP_SERVER,
        "steps": steps,
    }


def display_datetime_sync() -> None:
    """Configura hora/fuso automáticos, troca o servidor e sincroniza."""
    info = collect_datetime_info()
    result = synchronize_ntp()

    if result["success"]:
        log_audit("ntp_sync", "Configuração e sincronização de data/hora concluídas")
    else:
        log_audit("ntp_sync", f"Falha na configuração de data/hora: {result['message']}")

    current_time = str(info["time"]).split(":")
    time_label = ":".join(current_time[:2])
    print(
        f"Data/Hora: {info['date']} {time_label} "
        f"({info['timezone']}, {info['utc_offset']})"
    )
    print("")

    steps = result.get("steps") or []
    if steps:
        print("ETAPAS DE CONFIGURAÇÃO")
        for name, ok, detail in steps:
            marker = "OK  " if ok else "FALHA"
            print(f"  [{marker}] {name}")
            if detail:
                for line in str(detail).splitlines():
                    if line.strip():
                        print(f"           {line.strip()}")
        print("")

    if result["success"]:
        print("Resultado: data/hora e fuso configurados e sincronizados")
    else:
        print(f"Resultado: {result['message']}")
    print(f"Servidor NTP: {result['server']}")

    automatic = check_automatic_sync()
    print(
        "Sincronização automática: "
        + ("ativada" if automatic["enabled"] else "desativada")
    )

    expired = check_expired_certificates()
    if expired > 0:
        print(f"Certificados SSL: {expired} expirado(s) — AVISO: renovar certificados")
    else:
        print("Certificados SSL: nenhum expirado")


def check_timezone() -> dict[str, str | bool]:
    """Verifica se o fuso horário está correto para o Brasil."""
    if platform.system() != "Windows":
        return {
            "correct": False,
            "timezone": "não disponível",
            "expected": "E. South America Standard Time",
        }
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-TimeZone).Id",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            creationflags=_creation_flags(),
            startupinfo=_startup_info(),
        )
        current_tz = (result.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return {
            "correct": False,
            "timezone": "erro ao consultar",
            "expected": "E. South America Standard Time",
        }
    expected = "E. South America Standard Time"
    return {"correct": current_tz == expected, "timezone": current_tz, "expected": expected}


def check_expired_certificates() -> int:
    """Conta certificados SSL expirados no repositório LocalMachine\\My."""
    if platform.system() != "Windows":
        return 0
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "@(Get-ChildItem -Path Cert:\\LocalMachine\\My "
                "-ErrorAction SilentlyContinue | "
                "Where-Object {$_.NotAfter -lt (Get-Date)}).Count",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            creationflags=_creation_flags(),
            startupinfo=_startup_info(),
        )
        return int((result.stdout or "0").strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        return 0


