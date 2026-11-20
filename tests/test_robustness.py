"""Testes de robustez — edge cases que nao devem crashar o app."""

import sys
sys.path.insert(0, "..")

import os
import platform
import tempfile
import shutil

from modules.temp_cleaner import clean_temp, _clean_directory, _clean_directory_preserving, ANOTA_PRESERVED_DIRS
from modules.report import build_report
from modules.speedtest import _curl_path, run_speed_test


def assert_no_crash(func, *args, **kwargs):
    """Verifica que func nao levanta excecao."""
    try:
        func(*args, **kwargs)
        return True
    except Exception as e:
        raise AssertionError(f"Crash em {func.__name__}: {type(e).__name__}: {e}")


# --- temp_cleaner ---

def test_temp_empty_env():
    """TEMP e APPDATA vazios nao devem crashar."""
    old_temp = os.environ.pop("TEMP", None)
    old_appdata = os.environ.pop("APPDATA", None)
    try:
        assert_no_crash(clean_temp)
    finally:
        if old_temp is not None:
            os.environ["TEMP"] = old_temp
        if old_appdata is not None:
            os.environ["APPDATA"] = old_appdata
    print("PASSOU: temp/appdata vazios")


def test_clean_nonexistent_dir():
    """Limpar pasta inexistente nao deve crashar."""
    result = _clean_directory("/caminho/que/nao/existe/123456")
    assert result["arquivos_deletados"] == 0
    print("PASSOU: pasta inexistente")


def test_clean_preserving_logs():
    """Pastas preservadas (logs, config) nao devem ser removidas."""
    base = tempfile.mkdtemp(prefix="anota_test_")
    try:
        for d in ["logs", "config", "Cache", "GPUCache"]:
            os.makedirs(os.path.join(base, d))
        open(os.path.join(base, "logs", "app.log"), "w").write("importante")
        open(os.path.join(base, "config", "settings.json"), "w").write('{"x":1}')
        open(os.path.join(base, "Cache", "c1.bin"), "w").write("x" * 1000)
        open(os.path.join(base, "root.tmp"), "w").write("z" * 500)

        _clean_directory_preserving(base, ANOTA_PRESERVED_DIRS)

        assert os.path.exists(os.path.join(base, "logs", "app.log")), "logs deveria existir"
        assert os.path.exists(os.path.join(base, "config", "settings.json")), "config deveria existir"
        assert not os.path.exists(os.path.join(base, "Cache")), "Cache deveria ter sido removido"
        assert not os.path.exists(os.path.join(base, "root.tmp")), "root.tmp deveria ter sido removido"
        print("PASSOU: logs e config preservados")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_clean_preserving_nested():
    """Pastas preservadas dentro de subpastas tambem nao devem ser removidas."""
    base = tempfile.mkdtemp(prefix="anota_nested_")
    try:
        os.makedirs(os.path.join(base, "sub", "logs"))
        open(os.path.join(base, "sub", "logs", "deep.log"), "w").write("deep")
        os.makedirs(os.path.join(base, "sub", "Cache"))
        open(os.path.join(base, "sub", "Cache", "c.bin"), "w").write("c")

        _clean_directory_preserving(base, ANOTA_PRESERVED_DIRS)

        assert os.path.exists(os.path.join(base, "sub", "logs", "deep.log")), "logs aninhado deveria existir"
        assert not os.path.exists(os.path.join(base, "sub", "Cache")), "Cache aninhado deveria ser removido"
        print("PASSOU: logs aninhados preservados")
    finally:
        shutil.rmtree(base, ignore_errors=True)


# --- report ---

def test_report_garbage_input():
    """Entrada com lixo nao deve crashar o relatorio."""
    r = build_report("asdfghjklpoiuytrewq\n123456789\n!!!@@@###")
    assert isinstance(r, str)
    print("PASSOU: garbage input no report")


def test_report_partial_sections():
    """Secoes sem separador completo nao devem crashar."""
    raw = "=" * 59 + "\nTITULO SEM FECHAMENTO\nconteudo solto"
    r = build_report(raw)
    assert isinstance(r, str)
    print("PASSOU: secao parcial")


def test_report_very_long():
    """Saida muito longa nao deve crashar."""
    raw = ""
    for i in range(100):
        raw += f"\n{'='*59}\nTESTE {i}\n{'='*59}\nlinha de conteudo {i}\n{'-'*59}\n"
    r = build_report(raw)
    assert isinstance(r, str)
    print("PASSOU: saida muito longa")


# --- speedtest ---

def test_speedtest_no_curl():
    """Se curl nao existe, deve mostrar erro amigavel, nao crashar."""
    if _curl_path() is None:
        try:
            run_speed_test()
            raise AssertionError("deveria ter levantado RuntimeError")
        except RuntimeError as e:
            assert "curl" in str(e).lower(), f"deveria mencionar curl: {e}"
            print("PASSOU: curl ausente tratado")
    else:
        print("SKIP: curl disponivel (nao pode testar ausencia)")


def test_speedtest_offline():
    """Sem rede deve retornar RuntimeError, nao crashar."""
    try:
        run_speed_test()
    except RuntimeError as e:
        assert isinstance(e, RuntimeError)
        print("PASSOU: offline tratado")
    except Exception as e:
        raise AssertionError(f"deveria ser RuntimeError, got {type(e).__name__}: {e}")
    else:
        print("PASSOU: online (teste real funcionou)")


if __name__ == "__main__":
    tests = [
        test_temp_empty_env,
        test_clean_nonexistent_dir,
        test_clean_preserving_logs,
        test_clean_preserving_nested,
        test_report_garbage_input,
        test_report_partial_sections,
        test_report_very_long,
        test_speedtest_no_curl,
        test_speedtest_offline,
    ]
    passed = 0
    failed = 0
    skipped = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FALHOU: {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            if "SKIP" in str(e) or "skip" in str(e).lower():
                print(f"SKIP: {t.__name__}: {e}")
                skipped += 1
            else:
                print(f"ERRO: {t.__name__}: {type(e).__name__}: {e}")
                failed += 1
    print(f"\n=== {passed} passaram, {failed} falharam, {skipped} skipados ===")
    if failed:
        sys.exit(1)
