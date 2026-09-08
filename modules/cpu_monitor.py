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
    """Mede a CPU e exibe somente a média das leituras.

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
    for reading_number in range(duration):
        readings.append(psutil.cpu_percent(interval=None))
        if reading_number < duration - 1:
            sleep(interval)

    average = sum(readings) / len(readings)
    print(f"CPU: média de {average:.1f}% em {duration} leituras")
    return average
