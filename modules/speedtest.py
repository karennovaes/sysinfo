"""Teste de velocidade da conexão com a internet."""

from __future__ import annotations

from typing import Any

try:
    import speedtest as _speedtest
except Exception:
    _speedtest = None


def run_speed_test() -> dict[str, float]:
    """Executa o teste e retorna ping, download e upload.

    O import ocorre dentro da função para que o aplicativo ainda possa iniciar
    e concluir as outras etapas quando a dependência estiver indisponível.
    """
    if _speedtest is None:
        raise RuntimeError(
            "A biblioteca speedtest-cli não está instalada. "
            "Execute: python -m pip install -r requirements.txt"
        )

    try:
        client: Any = _speedtest.Speedtest()
        client.get_best_server()
        download_mbps = client.download() / 1_000_000
        upload_mbps = client.upload() / 1_000_000
        ping_ms = float(client.results.ping)
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
