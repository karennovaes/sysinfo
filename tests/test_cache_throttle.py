"""Testa o throttle do on_progress e o drain da fila em _process_queue.

Cenários:
1. on_progress é chamado no máximo a cada 100 arquivos (throttle)
2. _process_queue drena todas as mensagens de uma vez (drain)
"""
import sys
sys.path.insert(0, "..")

import os
import tempfile
import shutil
import queue
import threading

from modules.temp_cleaner import _clean_directory


def test_throttle_progress():
    """on_progress só deve ser chamado a cada 100 arquivos + 1 no final."""
    base = tempfile.mkdtemp(prefix="throttle_test_")
    try:
        # Cria 350 arquivos
        for i in range(350):
            open(os.path.join(base, f"file_{i}.tmp"), "w").write("x" * 10)

        calls = []
        def on_progress(count, mb):
            calls.append(count)

        _clean_directory(base, on_progress=on_progress)

        # Com throttle a cada 100: deve chamar em 100, 200, 300 e no final (350)
        # Ou seja, no máximo 5 chamadas para 350 arquivos
        assert len(calls) <= 5, f"Muitas chamadas: {len(calls)} (esperava <= 5)"
        assert len(calls) >= 3, f"Poucas chamadas: {len(calls)} (esperava >= 3)"
        # O último call deve ter o total
        assert calls[-1] == 350, f"Último call: {calls[-1]} (esperava 350)"
        # Nenhum call intermediário deve ter count não-múltiplo de 100
        for c in calls[:-1]:
            assert c % 100 == 0, f"Call intermediário {c} não é múltiplo de 100"
        print(f"PASSOU: throttle com {len(calls)} calls para 350 arquivos")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_throttle_few_files():
    """Com poucos arquivos, on_progress deve ser chamado pelo menos no final."""
    base = tempfile.mkdtemp(prefix="throttle_few_")
    try:
        for i in range(5):
            open(os.path.join(base, f"f{i}.tmp"), "w").write("y")

        calls = []
        _clean_directory(base, on_progress=lambda c, m: calls.append(c))

        # 5 arquivos: nenhum múltiplo de 100, mas o call final deve acontecer
        assert len(calls) >= 1, "Deveria ter pelo menos 1 call (final)"
        assert calls[-1] == 5, f"Último call: {calls[-1]} (esperava 5)"
        print(f"PASSOU: poucos arquivos, {len(calls)} call(s), último = {calls[-1]}")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_drain_all_messages():
    """_process_queue deve drenar todas as mensagens pendentes de uma vez."""
    class FakeRoot:
        def __init__(self):
            self._after_callbacks = []
        def after(self, ms, cb):
            self._after_callbacks.append(cb)

    class FakeApp:
        def __init__(self):
            self.root = FakeRoot()
            self._result_queue = queue.Queue()
            self._operation_gen = 1
            self._busy = True
            self._stop_event = threading.Event()
            self._active_screen = "computer"
            self._pending_tool_output = ""
            self._session_output = ""
            self._progress_total = 1
            self._progress_current = 0
            self._progress_labels = {}
            self._progress_bars = {}
            self._outputs = {"computer": None}
            self._hide_progress_called = False
            self._set_ready_called = False

        def _append_output(self, screen, text):
            pass
        def _hide_progress(self):
            self._hide_progress_called = True
        def _set_tool_ready(self):
            self._set_ready_called = True
        def _progress_name(self, title):
            return title

        # Importa o método real de helpers
        from gui.helpers import SystemInfoBase
        _process_queue = SystemInfoBase._process_queue

    app = FakeApp()

    # Enfileira: 500 mensagens de progresso + 1 output + 1 done
    for i in range(500):
        app._result_queue.put(("progress", f"Limpando... {i} arquivos"))
    app._result_queue.put(("output", "RESULTADO", 1))
    app._result_queue.put(("done", None, 1))

    # Deve drenar tudo em uma única chamada
    app._process_queue()

    # Após o drain, deve ter terminado (set_tool_ready chamado)
    assert app._set_ready_called, "Deveria ter chamado _set_tool_ready"
    assert app._hide_progress_called, "Deveria ter chamado _hide_progress"
    assert app._pending_tool_output == "RESULTADO", f"Output: '{app._pending_tool_output}'"
    # Não deve ter reagendado (busy=False após done)
    assert len(app.root._after_callbacks) == 0, "Não deveria reagendar após done"
    print("PASSOU: drain drenou 502 mensagens em 1 ciclo")


if __name__ == "__main__":
    test_throttle_progress()
    test_throttle_few_files()
    test_drain_all_messages()
    print("\n=== TODOS PASSARAM ===")
