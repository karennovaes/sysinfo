"""Aba Rede."""

from __future__ import annotations

import platform
import subprocess
from contextlib import redirect_stdout
from io import StringIO

try:
    import tkinter as tk
except ImportError:
    tk = None

from modules.config import PRINTERS_COMMAND
from modules.security import log_audit
from modules.theme import *
from .helpers import (
    SystemInfoBase, _clear_print_queue, _creation_flags, _run_command_capture, _startup_info,
)
from modules.network_tools import (
    display_anota_connection, display_firewall_status, display_flush_dns,
    display_proxy_vpn_status,
)


class NetworkTabMixin:
    """Métodos e construção da aba correspondente."""

    def _build_network_frame(self) -> None:
            _, body = self._build_screen_shell(self.network_frame, "Rede — Anota AI")
            definitions = [
                ("Flush DNS", self._flush_dns),
                ("Verificar Firewall", self._check_firewall),
                ("Verificar Proxy/VPN", self._check_proxy_vpn),
                ("Testar Conexão Anota AI", self._test_anota_connection),
                ("Ipconfig", self._ipconfig),
                ("ARP -a", self._arp),
                ("MSCONFIG", self._open_msconfig),
            ]
            self._build_action_screen(body, "network", definitions)

    def _ipconfig(self) -> None:
            self._start_command_thread(
                "network", "Ipconfig", lambda: self._queue_command_output(_run_command_capture(["ipconfig", "/all"]))
            )

    def _arp(self) -> None:
            self._start_command_thread(
                "network", "ARP -a", lambda: self._queue_command_output(_run_command_capture(["arp", "-a"]))
            )

    def _open_msconfig(self) -> None:
            self._start_command_thread("network", "MSCONFIG", self._open_msconfig_worker)

    def _open_msconfig_worker(self) -> None:
            if platform.system() != "Windows":
                self._queue_command_output("Disponível apenas no Windows")
                return
            subprocess.Popen(["msconfig"], creationflags=_creation_flags(), startupinfo=_startup_info())
            self._queue_command_output("Abrindo MSCONFIG...")

    def _flush_dns(self) -> None:
            self._start_command_thread(
                "network", "Flush DNS", lambda: self._queue_command_output_capture(display_flush_dns)
            )

    def _check_firewall(self) -> None:
            self._start_command_thread(
                "network", "Verificar Firewall", lambda: self._queue_command_output_capture(display_firewall_status)
            )

    def _check_proxy_vpn(self) -> None:
            self._start_command_thread(
                "network",
                "Verificar Proxy/VPN",
                lambda: self._queue_command_output_capture(display_proxy_vpn_status),
            )

    def _test_anota_connection(self) -> None:
            self._start_command_thread(
                "network", "Testar Conexão Anota AI", lambda: self._queue_command_output_capture(display_anota_connection)
            )
