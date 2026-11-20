"""Testa o isolamento de geracoes entre testes apos Parar.

Cenarios:
1. Teste normal completa corretamente
2. Parar teste A, iniciar B, A nao vaza
3. Parar zera _pending_tool_output
4. Parar A, iniciar B, iniciar C, so C aparece
5. redirect_stdout com lock: A e B simultaneos nao misturam
"""

import queue
import threading
import time
import io
from contextlib import redirect_stdout


class FakeApp:
    def __init__(self):
        self._result_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._operation_gen = 0
        self._current_gen = 0
        self._busy = False
        self._pending_tool_output = ""
        self._output_log = []
        self._stdout_lock = threading.Lock()

    def _start_operation(self, label, sections, screen="computer"):
        if self._busy:
            return
        self._operation_gen += 1
        gen = self._operation_gen
        self._stop_event.clear()
        try:
            while True:
                self._result_queue.get_nowait()
        except queue.Empty:
            pass
        self._busy = True
        self._current_gen = gen
        self._pending_tool_output = ""
        worker = threading.Thread(
            target=self._run_sections, args=(sections, gen), daemon=True
        )
        worker.start()

    def _run_sections(self, sections, gen=0):
        for title, action in sections:
            if self._stop_event.is_set() or gen != self._operation_gen:
                break
            self._result_queue.put(("progress", title, gen))
            captured = io.StringIO()
            with self._stdout_lock:
                with redirect_stdout(captured):
                    try:
                        action()
                    except Exception as exc:
                        print(f"Erro: {exc}")
            if not self._stop_event.is_set() and gen == self._operation_gen:
                self._result_queue.put((
                    "output",
                    f"CONTEUDO DE {title}",
                    gen,
                ))
        if not self._stop_event.is_set() and gen == self._operation_gen:
            self._result_queue.put(("done", None, gen))

    def _stop_operation(self):
        self._stop_event.set()
        self._busy = False
        self._pending_tool_output = ""
        try:
            while True:
                self._result_queue.get_nowait()
        except queue.Empty:
            pass

    def _process_once(self):
        try:
            msg = self._result_queue.get_nowait()
            mt = msg[0] if len(msg) > 0 else None
            pl = msg[1] if len(msg) > 1 else None
            mg = msg[2] if len(msg) > 2 else None
        except queue.Empty:
            return False
        if mg is not None and mg != self._operation_gen:
            return True
        if mt == "output" and pl:
            self._pending_tool_output += pl
        elif mt == "done":
            self._output_log.append(self._pending_tool_output)
            self._busy = False
            self._pending_tool_output = ""
            return False
        return True

    def _drain(self, n=1000):
        for _ in range(n):
            if not self._process_once():
                break


def test_normal():
    app = FakeApp()
    def simple():
        pass
    app._start_operation("Teste", [("TESTE", simple)], "computer")
    time.sleep(0.2)
    app._drain_queue = app._drain
    app._drain()
    assert len(app._output_log) == 1
    assert "TESTE" in app._output_log[0]
    print("PASSOU: completou normalmente")


def test_stop_no_leak():
    """Parar A, iniciar B, A termina depois — A nao vaza."""
    app = FakeApp()
    def slow_a():
        time.sleep(0.5)
    def fast_b():
        pass
    app._start_operation("A", [("TESTE A", slow_a)], "computer")
    time.sleep(0.05)
    app._stop_operation()
    app._start_operation("B", [("TESTE B", fast_b)], "computer")
    time.sleep(0.15)
    app._drain()
    time.sleep(0.5)
    app._drain()
    assert len(app._output_log) == 1, f"esperava 1, got {len(app._output_log)}"
    assert "TESTE B" in app._output_log[0], f"B deveria estar: {app._output_log[0]}"
    assert "TESTE A" not in app._output_log[0], f"A vazou: {app._output_log[0]}"
    print("PASSOU: A nao vazou para B")


def test_stop_clears_pending():
    app = FakeApp()
    def slow():
        time.sleep(0.3)
    app._start_operation("Teste", [("TESTE", slow)], "computer")
    time.sleep(0.05)
    app._pending_tool_output = "parcial antigo"
    app._stop_operation()
    assert app._pending_tool_output == ""
    print("PASSOU: pending limpo")


def test_stdout_lock():
    """Duas threads simultaneas com redirect_stdout + lock nao misturam."""
    app = FakeApp()
    results = {}

    def worker(name, delay):
        captured = io.StringIO()
        with app._stdout_lock:
            with redirect_stdout(captured):
                time.sleep(delay)
                print(f"OUTPUT_{name}")
        results[name] = captured.getvalue()

    t1 = threading.Thread(target=worker, args=("A", 0.1), daemon=True)
    t2 = threading.Thread(target=worker, args=("B", 0.0), daemon=True)
    t1.start()
    time.sleep(0.02)
    t2.start()
    t1.join()
    t2.join()

    assert results.get("A") == "OUTPUT_A\n", f"A: '{results.get('A')}'"
    assert results.get("B") == "OUTPUT_B\n", f"B: '{results.get('B')}'"
    assert "OUTPUT_A" not in results.get("B", ""), "A vazou para B!"
    print("PASSOU: lock isola redirect_stdout entre threads")


if __name__ == "__main__":
    test_normal()
    test_stop_no_leak()
    test_stop_clears_pending()
    test_stdout_lock()
    print("\n=== TODOS PASSARAM ===")
