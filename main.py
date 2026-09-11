"""Ponto de entrada do Diagnóstico do Sistema."""

from __future__ import annotations

import io
import os
import platform
import subprocess
import sys

if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

import ctypes

from modules.compatibility_check import display_compatibility_check
from modules.cpu_monitor import monitor_cpu
from modules.datetime_sync import display_datetime_sync
from modules.security import log_audit
from modules.speedtest import display_speed_test
from modules.system_info import collect_system_info, display_system_info
from modules.temp_cleaner import display_temp_cleaner

TITLE = "=== Suporte Tools ==="
SEPARATOR = "-" * len(TITLE)


def _ensure_admin() -> None:
    """Re-inicia o programa com privilégios de administrador no Windows."""
    if platform.system() != "Windows":
        return
    if ctypes.windll.shell32.IsUserAnAdmin():
        return
    parameters = subprocess.list2cmdline(sys.argv)
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, parameters, None, 1
    )
    sys.exit(0)


def clear_screen() -> None:
    """Limpa a tela no início, respeitando o sistema operacional."""
    if platform.system() == "Windows":
        try:
            subprocess.run(["cls"], shell=False, check=False, timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass
    elif os.environ.get("TERM"):
        try:
            subprocess.run(["clear"], shell=False, check=False, timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass


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
    log_audit("program_start", "Diagnóstico do Sistema iniciado (modo terminal)")
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
    run_section("LIMPEZA DE ARQUIVOS TEMPORÁRIOS", display_temp_cleaner)
    log_audit("program_end", "Diagnóstico do Sistema encerrado (modo terminal)")
    wait_before_exit()


if __name__ == "__main__":
    main()
