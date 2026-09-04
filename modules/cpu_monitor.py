"""Monitoramento simples do uso da CPU."""

from __future__ import annotations

import time
from collections.abc import Callable

import psutil


def monitor_cpu(
    duration: int = 10,
    interval: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> float:
    """Mede e exibe o uso da CPU uma vez por segundo.

    Args:
        duration: quantidade de leituras a realizar.
        interval: intervalo, em segundos, entre leituras.
        sleep: função de espera injetável para testes.

    Returns:
        Média das leituras em porcentagem.
    """
    if duration <= 0:
        raise ValueError("A duração deve ser maior que zero.")
    if interval < 0:
        raise ValueError("O intervalo não pode ser negativo.")

    readings: list[float] = []
    print(f"Monitorando a CPU por aproximadamente {duration} segundos...")
    for second in range(1, duration + 1):
        usage = psutil.cpu_percent(interval=None)
        readings.append(usage)
        print(f"[{second:02d}/{duration:02d}] Uso da CPU: {usage:.1f}%")
        if second < duration:
            sleep(interval)

    average = sum(readings) / len(readings)
    print(f"Média de uso da CPU: {average:.1f}%")
    return average
