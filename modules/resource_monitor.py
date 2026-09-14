"""Monitor de recursos em tempo real estilo Gerenciador de Tarefas."""

from __future__ import annotations

import tkinter as tk
from collections import deque
from tkinter import ttk
from typing import Callable

import psutil

from modules.theme import (
    ACCENT_GREEN,
    BG_LIGHT,
    BG_WHITE,
    FONT_HEADING,
    FONT_STATUS,
    PRIMARY_COLOR,
    TEXT_DARK,
)


class ResourceMonitorWidget:
    """Widget embutido com gráficos de CPU, memória e disco em tempo real."""

    MAX_POINTS = 60
    UPDATE_INTERVAL = 1000
    GRAPH_HEIGHT = 80
    GRAPH_WIDTH = 300

    def __init__(
        self, container: tk.Frame, on_close: Callable[[], None] | None = None
    ) -> None:
        self.container = container
        self._on_close = on_close
        self._cpu_data: deque[float] = deque(
            [0.0] * self.MAX_POINTS, maxlen=self.MAX_POINTS
        )
        self._mem_data: deque[float] = deque(
            [0.0] * self.MAX_POINTS, maxlen=self.MAX_POINTS
        )
        self._disk_data: deque[float] = deque(
            [0.0] * self.MAX_POINTS, maxlen=self.MAX_POINTS
        )
        self._prev_disk_bytes: tuple[int, int] | None = None

        self._build_ui()
        self._running = True
        self._after_id: str | None = None
        self._update()

    def _build_ui(self) -> None:
        """Constrói os cartões de CPU, memória e disco no container."""
        # Botão Parar no topo.
        button_bar = tk.Frame(self.container, bg=BG_WHITE)
        button_bar.pack(fill="x", padx=10, pady=(10, 5))

        stop_top_btn = ttk.Button(
            button_bar,
            text="Parar",
            command=self._close,
            style="Rounded.TButton",
        )
        stop_top_btn.pack(side="left")

        # Canvas com scrollbar para comportar os três gráficos e o botão.
        canvas = tk.Canvas(
            self.container,
            bg=BG_WHITE,
            highlightthickness=0,
            bd=0,
        )
        scrollbar = tk.Scrollbar(
            self.container,
            orient="vertical",
            command=canvas.yview,
            troughcolor=BG_LIGHT,
            activebackground=PRIMARY_COLOR,
            relief="flat",
            borderwidth=0,
        )
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)

        # Frame interno onde os cartões e o botão são empacotados.
        inner = tk.Frame(canvas, bg=BG_WHITE)
        inner_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        # Atualiza a região de rolagem quando o conteúdo muda.
        def _configure_scroll_region(event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _configure_inner_width(event: tk.Event) -> None:
            # Faz o frame interno acompanhar a largura do canvas.
            canvas.itemconfig(inner_window, width=event.width)

        inner.bind("<Configure>", _configure_scroll_region)
        canvas.bind("<Configure>", _configure_inner_width)

        self._scrollable_container = inner

        self._build_graph_card("CPU", PRIMARY_COLOR, 0)
        self._build_graph_card("Memória", ACCENT_GREEN, 1)
        self._build_graph_card("Disco", TEXT_DARK, 2)



    def _build_graph_card(self, label: str, color: str, index: int) -> None:
        """Cria um cartão com valor percentual e gráfico de linha."""
        frame = tk.Frame(self._scrollable_container, bg=BG_WHITE, padx=15, pady=5)
        frame.pack(fill="x", padx=10, pady=(10 if index == 0 else 5))

        header = tk.Frame(frame, bg=BG_WHITE)
        header.pack(fill="x")

        title = tk.Label(
            header,
            text=label,
            bg=BG_WHITE,
            fg=TEXT_DARK,
            font=FONT_HEADING,
            anchor="w",
        )
        title.pack(side="left")

        value_label = tk.Label(
            header,
            text="0%",
            bg=BG_WHITE,
            fg=color,
            font=FONT_HEADING,
            anchor="e",
        )
        value_label.pack(side="right")

        canvas = tk.Canvas(
            frame,
            width=self.GRAPH_WIDTH,
            height=self.GRAPH_HEIGHT,
            bg=BG_LIGHT,
            highlightthickness=1,
            highlightbackground="#E0E0E0",
        )
        canvas.pack(fill="x", pady=(5, 0))

        detail_label = tk.Label(
            frame,
            text="",
            bg=BG_WHITE,
            fg=TEXT_DARK,
            font=FONT_STATUS,
            anchor="w",
        )
        detail_label.pack(fill="x", pady=(2, 0))

        if index == 0:
            self._cpu_canvas = canvas
            self._cpu_value = value_label
            self._cpu_detail = detail_label
            self._cpu_color = color
        elif index == 1:
            self._mem_canvas = canvas
            self._mem_value = value_label
            self._mem_detail = detail_label
            self._mem_color = color
        else:
            self._disk_canvas = canvas
            self._disk_value = value_label
            self._disk_detail = detail_label
            self._disk_color = color

    def _update(self) -> None:
        """Coleta dados e redesenha os gráficos a cada segundo."""
        if not self._running:
            return

        cpu_percent = psutil.cpu_percent(interval=None)
        self._cpu_data.append(cpu_percent)
        self._cpu_value.configure(text=f"{cpu_percent:.1f}%")
        self._draw_graph(self._cpu_canvas, self._cpu_data, self._cpu_color)

        mem = psutil.virtual_memory()
        self._mem_data.append(mem.percent)
        self._mem_value.configure(text=f"{mem.percent:.1f}%")
        used_gb = mem.used / (1024**3)
        total_gb = mem.total / (1024**3)
        self._mem_detail.configure(text=f"{used_gb:.1f} GB / {total_gb:.1f} GB")
        self._draw_graph(self._mem_canvas, self._mem_data, self._mem_color)

        disk_percent = self._read_disk_activity()
        self._disk_data.append(disk_percent)
        self._disk_value.configure(text=f"{disk_percent:.1f}%")
        self._disk_detail.configure(text="Atividade de leitura e escrita")
        self._draw_graph(self._disk_canvas, self._disk_data, self._disk_color)

        self._after_id = self.container.after(self.UPDATE_INTERVAL, self._update)

    def _read_disk_activity(self) -> float:
        """Converte a atividade de disco entre leituras em uma escala percentual."""
        try:
            disk_counters = psutil.disk_io_counters()
            if disk_counters is None:
                return 0.0
            current = (disk_counters.read_bytes, disk_counters.write_bytes)
            if self._prev_disk_bytes is None:
                self._prev_disk_bytes = current
                return 0.0
            read_bytes = max(0, current[0] - self._prev_disk_bytes[0])
            write_bytes = max(0, current[1] - self._prev_disk_bytes[1])
            self._prev_disk_bytes = current
            total_io_mb = (read_bytes + write_bytes) / (1024**2)
            # Uma leitura ocorre a cada segundo; 100 MB/s representa 100%.
            return min(100.0, total_io_mb)
        except Exception:
            return 0.0

    def _draw_graph(
        self, canvas: tk.Canvas, data: deque[float], color: str
    ) -> None:
        """Desenha um gráfico de linha preenchido no Canvas."""
        canvas.delete("all")
        width = self.GRAPH_WIDTH
        height = self.GRAPH_HEIGHT
        values = list(data)
        points: list[float] = []

        for index, value in enumerate(values):
            x = (index / (len(values) - 1)) * width if len(values) > 1 else 0
            bounded_value = max(0.0, min(100.0, value))
            y = height - (bounded_value / 100.0) * height
            points.extend([x, y])

        for percentage in (25, 50, 75):
            y = height - (percentage / 100.0) * height
            canvas.create_line(0, y, width, y, fill="#E8E8E8", dash=(2, 2))

        if len(points) >= 4:
            fill_points = points + [width, height, 0, height]
            canvas.create_polygon(
                *fill_points, fill=color, outline="", stipple="gray50"
            )

        if len(points) >= 2:
            canvas.create_line(*points, fill=color, width=2)

    def _close(self) -> None:
        """Interrompe as atualizações e chama o callback de encerramento."""
        self._running = False
        if self._after_id is not None:
            self.container.after_cancel(self._after_id)
            self._after_id = None

        if self._on_close is not None:
            self._on_close()
        else:
            self.container.destroy()


def create_resource_monitor(
    container: tk.Frame, on_close: Callable[[], None] | None = None
) -> ResourceMonitorWidget:
    """Cria o monitor de recursos dentro do container fornecido."""
    return ResourceMonitorWidget(container, on_close)
