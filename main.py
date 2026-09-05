"""Ponto de entrada do Diagnóstico do Sistema."""

from __future__ import annotations

import os
import platform

from modules.cpu_monitor import monitor_cpu
from modules.speedtest import display_speed_test
from modules.system_info import collect_system_info, display_system_info

TITLE = "=== Diagnóstico do Sistema ==="
SEPARATOR = "-" * len(TITLE)


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
    clear_screen()
    print(TITLE)
    print("Coleta de informações do computador e da conexão de internet.")

    run_section(
        "INFORMAÇÕES DO SISTEMA",
        lambda: display_system_info(collect_system_info()),
    )
    run_section("MONITOR DE CPU", lambda: monitor_cpu(duration=10, interval=1.0))
    run_section("TESTE DE VELOCIDADE DA INTERNET", display_speed_test)
    wait_before_exit()


if __name__ == "__main__":
    main()
