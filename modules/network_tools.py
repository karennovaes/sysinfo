"""Ferramentas de rede usadas pelo diagnóstico do Anota AI."""

from __future__ import annotations

import platform
import re
import subprocess


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0


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


def _run(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str] | None:
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
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Erro ao executar {' '.join(command)}: {exc}")
        return None


def display_flush_dns() -> None:
    if platform.system() != "Windows":
        print("Disponível apenas no Windows.")
        return
    result = _run(["ipconfig", "/flushdns"])
    if result is not None:
        print((result.stdout or result.stderr or "Comando executado sem saída.").strip())


def _profile_states(output: str) -> list[tuple[str, str]]:
    profiles: list[tuple[str, str]] = []
    current = "Perfil não identificado"
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.casefold().endswith("profile settings"):
            current = stripped.rsplit(" ", 2)[0]
        match = re.search(r"(?:State|Estado)\s*:?\s+(ON|OFF|ATIVADO|DESATIVADO)", stripped, re.IGNORECASE)
        if match:
            profiles.append((current, match.group(1)))
    return profiles


def display_firewall_status() -> None:
    if platform.system() != "Windows":
        print("Disponível apenas no Windows.")
        return
    result = _run(["netsh", "advfirewall", "show", "allprofiles", "state"])
    if result is None:
        return
    output = (result.stdout or result.stderr or "").strip()
    states = _profile_states(output)
    if states:
        for profile, state in states:
            active = state.casefold() in {"on", "ativado"}
            print(f"{profile}: {'ATIVO' if active else 'INATIVO'}")
    else:
        print("Não foi possível interpretar os perfis. Saída do Windows:")
        print(output or "Sem saída.")



def display_proxy_vpn_status() -> None:
    """Verifica proxy, VPN conectada e adaptadores virtuais no Windows."""
    if platform.system() != "Windows":
        print("Disponível apenas no Windows.")
        return

    internet_settings_key = (
        r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    )

    # --- Proxy do Windows -------------------------------------------------
    print("PROXY DO WINDOWS")
    proxy_enable_result = _run(["reg", "query", internet_settings_key, "/v", "ProxyEnable"])
    proxy_enabled = False
    if proxy_enable_result is not None and proxy_enable_result.returncode == 0:
        proxy_match = re.search(
            r"ProxyEnable\s+REG_DWORD\s+0x([0-9a-f]+)",
            proxy_enable_result.stdout or "",
            re.IGNORECASE,
        )
        proxy_enabled = bool(proxy_match and int(proxy_match.group(1), 16) == 1)

    proxy_server = ""
    proxy_server_result = _run(
        ["reg", "query", internet_settings_key, "/v", "ProxyServer"]
    )
    if proxy_server_result is not None and proxy_server_result.returncode == 0:
        server_match = re.search(
            r"^\s*ProxyServer\s+REG_SZ\s+(.+?)\s*$",
            proxy_server_result.stdout or "",
            re.IGNORECASE | re.MULTILINE,
        )
        if server_match:
            proxy_server = server_match.group(1).strip()

    auto_config = ""
    auto_config_result = _run(
        ["reg", "query", internet_settings_key, "/v", "AutoConfigURL"]
    )
    if auto_config_result is not None and auto_config_result.returncode == 0:
        auto_match = re.search(
            r"^\s*AutoConfigURL\s+REG_SZ\s+(.+?)\s*$",
            auto_config_result.stdout or "",
            re.IGNORECASE | re.MULTILINE,
        )
        if auto_match:
            auto_config = auto_match.group(1).strip()

    if proxy_enabled:
        print("  Proxy: ATIVO")
        if proxy_server:
            print(f"  Servidor: {proxy_server}")
        if auto_config:
            print(f"  Auto-config: {auto_config}")
        print("  AVISO: O proxy pode interferir na comunicação do Anota AI.")
    else:
        print("  Proxy: inativo")
        if auto_config:
            print(f"  Auto-config: {auto_config}")

    print()

    # --- VPN conectada ---------------------------------------------------
    print("VPN")
    vpn_result = _run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "Get-VpnConnection | "
                "Where-Object {$_.ConnectionStatus -eq 'Connected'} | "
                "Select-Object Name,ConnectionStatus | Format-List"
            ),
        ]
    )
    vpn_output = (vpn_result.stdout if vpn_result is not None else "") or ""
    if vpn_output.strip():
        print("  VPN ativa detectada:")
        for line in vpn_output.strip().splitlines():
            stripped = line.strip()
            if stripped:
                print(f"  {stripped}")
        print("  AVISO: A VPN pode bloquear ou redirecionar o tráfego do Anota AI.")
    else:
        print("  Nenhuma VPN conectada.")

    print()

    # --- Adaptadores virtuais suspeitos ----------------------------------
    print("ADAPTADORES VIRTUAIS")
    adapter_result = _run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | "
                "Select-Object Name,InterfaceDescription | Format-List"
            ),
        ]
    )
    adapter_output = (adapter_result.stdout if adapter_result is not None else "") or ""
    vpn_keywords = (
        "vpn",
        "virtual",
        "tap",
        "hamachi",
        "zero tier",
        "zerotier",
        "wireguard",
        "openvpn",
        "cisco",
        "forticlient",
        "pulse",
    )
    found_adapters = False
    for line in adapter_output.splitlines():
        stripped = line.strip()
        if stripped and any(keyword in stripped.casefold() for keyword in vpn_keywords):
            print(f"  {stripped}")
            found_adapters = True
    if not found_adapters:
        print("  Nenhum adaptador virtual suspeito ativo.")


def display_anota_connection() -> None:
    command = ["ping", "app.anota.ai", "-n", "4"] if platform.system() == "Windows" else ["ping", "-c", "4", "app.anota.ai"]
    result = _run(command, timeout=30)
    if result is None:
        return
    output = (result.stdout or result.stderr or "").strip()
    print(output or "Sem resposta.")
    if result.returncode != 0:
        print("Conexão não estabelecida.")
        return
    match = re.search(r"(?:Average|Média)[^=]*=\s*(<\s*1|\d+)\s*ms", output, re.IGNORECASE)
    latency = f"{match.group(1).replace(' ', '')} ms" if match else "não identificada"
    print(f"Conexão estabelecida. Latência média: {latency}.")
