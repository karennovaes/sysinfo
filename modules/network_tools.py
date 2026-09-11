"""Ferramentas de rede usadas pelo diagnóstico do Anota AI."""

from __future__ import annotations

import platform
import re
import subprocess


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0


def _run(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=_creation_flags(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Erro ao executar {' '.join(command)}: {exc}")
        return None


def display_flush_dns() -> None:
    print("FLUSH DNS")
    print("-" * 64)
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
    print("STATUS DO FIREWALL")
    print("-" * 64)
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


def display_anota_connection() -> None:
    print("TESTE DE CONEXÃO ANOTA AI")
    print("-" * 64)
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
