"""Ponto de entrada do Diagnóstico do Sistema."""

from __future__ import annotations

import io
import sys

if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

import ctypes
import os
import platform

from modules.compatibility_check import display_compatibility_check
from modules.cpu_monitor import monitor_cpu
from modules.datetime_sync import display_datetime_sync
from modules.speedtest import display_speed_test
from modules.system_info import collect_system_info, display_system_info

TITLE = "=== Diagnóstico do Sistema ==="
SEPARATOR = "-" * len(TITLE)


def _ensure_admin():
    """Re-inicia o programa com privilégios de administrador no Windows."""
    if platform.system() != "Windows":
        return
    if ctypes.windll.shell32.IsUserAnAdmin():
        return
    # Solicita elevação UAC e re-inicia
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit(0)


def clear_screen() -> None:
    """Limpa a tela no início, respeitando o sistema operacional."""
    command = "cls" if platform.system() == "Windows" else "clear"
    if os.environ.get("TERM") or platform.system() == "Windows":
        os.system(command)


def run_section(title: str, action) -> None:
    """Executa uma seção isolando falhas das demais etapas."""
    print(f"\n{SEPARATOR}\n{title}\n{SEPARATOR}")
    try:
        action()
    except Exception as exc:
        print(f"Não foi possível concluir esta seção: {exc}")


def wait_before_exit() -> None:
    """Mantém a janela aberta, inclusive ao executar o .exe remotamente."""
    try:
        input("\nDiagnóstico concluído. Pressione Enter para fechar...")
    except EOFError:
        print("\nEntrada não interativa detectada; encerrando.")


def main() -> None:
    """Orquestra as etapas do diagnóstico."""
    _ensure_admin()
    clear_screen()
    print(TITLE)
    print("Coleta de informações do computador e da conexão de internet.")

    run_section(
        "VERIFICAÇÃO DE COMPATIBILIDADE — ANOTA AI",
        display_compatibility_check,
    )
    run_section(
        "INFORMAÇÕES DO SISTEMA",
        lambda: display_system_info(collect_system_info()),
    )
    run_section("MONITOR DE CPU", lambda: monitor_cpu(duration=10, interval=1.0))
    run_section("DATA, HORA E SINCRONIZAÇÃO", display_datetime_sync)
    run_section("TESTE DE VELOCIDADE DA INTERNET", display_speed_test)
    wait_before_exit()


if __name__ == "__main__":
    main()
