"""Teste de velocidade da conexão com a internet.

O speedtest-cli abre subprocessos internamente e, quando empacotado com
PyInstaller em modo --onefile, o executável filho não encontra o
``base_library.zip`` extraído em ``_MEIxxxx`` — por isso o teste falhava
dentro do executável.

A solução é usar o ``curl`` que já vem no Windows 10/11 (curl.exe em
System32). Ele mede download e upload sem depender de bibliotecas Python
extras e funciona igual no código fonte e no executável.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import time

# Arquivos de teste públicos e estáveis.
DOWNLOAD_URL = "https://speed.cloudflare.com/__down?bytes=10000000"  # 10 MB
UPLOAD_URL = "https://speed.cloudflare.com/__up"
PING_URL = "https://speed.cloudflare.com/__down?bytes=0"
TIMEOUT = 30


def _creation_flags() -> int:
    """Evita janela de console ao chamar o curl no Windows."""
    if platform.system() == "Windows":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def _curl_path() -> str | None:
    """Localiza o curl disponível no sistema."""
    found = shutil.which("curl")
    if found:
        return found
    if platform.system() == "Windows":
        candidate = r"C:\Windows\System32\curl.exe"
        if os.path.isfile(candidate):
            return candidate
    return None


def _run_curl(args: list[str], timeout: int = TIMEOUT) -> subprocess.CompletedProcess[str]:
    """Executa o curl com as flags de ocultação de console."""
    curl = _curl_path()
    if curl is None:
        raise RuntimeError(
            "curl não encontrado no sistema. Atualize o Windows ou instale o curl."
        )
    return subprocess.run(
        [curl, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        creationflags=_creation_flags(),
    )


def _measure_ping() -> float:
    """Mede a latência até o servidor de teste, em ms."""
    result = _run_curl(
        [
            "-s", "-o", os.devnull,
            "-w", "%{time_connect}",
            "--max-time", "10",
            PING_URL,
        ],
        timeout=15,
    )
    if result.returncode != 0:
        return 0.0
    try:
        seconds = float(result.stdout.strip())
    except ValueError:
        return 0.0
    return seconds * 1000


def _measure_download() -> float:
    """Baixa 10 MB e retorna a velocidade em Mbps."""
    start = time.perf_counter()
    result = _run_curl(
        [
            "-s", "-o", os.devnull,
            "-w", "%{size_download}",
            "--max-time", str(TIMEOUT),
            DOWNLOAD_URL,
        ]
    )
    elapsed = time.perf_counter() - start
    if result.returncode != 0:
        raise RuntimeError(f"download falhou (código {result.returncode})")
    try:
        size = int(result.stdout.strip())
    except ValueError:
        return 0.0
    if elapsed <= 0 or size == 0:
        return 0.0
    return (size * 8) / elapsed / 1_000_000


def _measure_upload() -> float:
    """Envia 2 MB e retorna a velocidade em Mbps."""
    payload = b"0" * (2 * 1024 * 1024)
    handle, path = tempfile.mkstemp(suffix=".bin")
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(payload)
        start = time.perf_counter()
        result = _run_curl(
            [
                "-s", "-o", os.devnull,
                "-w", "%{size_upload}",
                "--max-time", str(TIMEOUT),
                "-X", "POST",
                "--data-binary", f"@{path}",
                UPLOAD_URL,
            ]
        )
        elapsed = time.perf_counter() - start
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    if result.returncode != 0:
        raise RuntimeError(f"upload falhou (código {result.returncode})")
    try:
        size = int(result.stdout.strip())
    except ValueError:
        size = len(payload)
    if elapsed <= 0 or size == 0:
        return 0.0
    return (size * 8) / elapsed / 1_000_000


def run_speed_test() -> dict[str, float]:
    """Executa o teste e retorna ping, download e upload."""
    try:
        ping_ms = _measure_ping()
        download_mbps = _measure_download()
        upload_mbps = _measure_upload()
    except Exception as exc:
        raise RuntimeError(f"não foi possível concluir o teste ({exc})") from exc

    return {
        "download_mbps": download_mbps,
        "upload_mbps": upload_mbps,
        "ping_ms": ping_ms,
    }


def display_speed_test() -> None:
    """Executa e exibe o resultado em uma única linha para o chat."""
    try:
        result = run_speed_test()
    except RuntimeError as exc:
        print(f"Internet: teste indisponível ({exc})")
        return

    ping = float(result["ping_ms"])
    ping_label = f"{ping:.0f}" if ping.is_integer() else f"{ping:.1f}"
    print(
        f"Internet: {result['download_mbps']:.1f} Mbps download, "
        f"{result['upload_mbps']:.1f} Mbps upload, {ping_label}ms ping"
    )
