"""Testes unitários dos módulos — cada função isolada com mocks."""

import sys
sys.path.insert(0, "..")

import os
import platform
import tempfile
import shutil
import subprocess
from unittest.mock import patch, MagicMock

# --- config ---

def test_config_values():
    """Config deve ter todas as URLs e nomes de arquivo."""
    from modules.config import (
        DESKTOP_URL, DESKTOP_FILENAME, DRIVER_URL, DRIVER_FILENAME,
        NETSTATGUI_URL, NETSTATGUI_FILENAME, PRINTERS_COMMAND,
    )
    assert DESKTOP_URL.startswith("https://"), "DESKTOP_URL deve ser HTTPS"
    assert DESKTOP_FILENAME.endswith(".exe"), "DESKTOP_FILENAME deve ser .exe"
    assert DRIVER_URL.startswith("https://"), "DRIVER_URL deve ser HTTPS"
    assert DRIVER_FILENAME.endswith(".exe"), "DRIVER_FILENAME deve ser .exe"
    assert NETSTATGUI_URL.startswith("https://"), "NETSTATGUI_URL deve ser HTTPS"
    assert NETSTATGUI_FILENAME.endswith(".exe"), "NETSTATGUI_FILENAME deve ser .exe"
    assert PRINTERS_COMMAND, "PRINTERS_COMMAND nao deve ser vazio"
    print("PASSOU: config tem URLs e nomes validos")


# --- theme ---

def test_theme_colors():
    """Theme deve ter cores em formato hex (#RRGGBB)."""
    from modules import theme
    color_attrs = [a for a in dir(theme) if a.isupper() and "COLOR" in a]
    assert len(color_attrs) >= 5, f"deveria ter 5+ cores, tem {len(color_attrs)}"
    for attr in color_attrs:
        val = getattr(theme, attr)
        if val:
            assert val.startswith("#"), f"{attr}={val} deveria ser hex"
    print(f"PASSOU: theme tem {len(color_attrs)} cores em formato hex")


def test_theme_fonts():
    """Theme deve ter fontes como tupla (familia, tamanho, estilo)."""
    from modules import theme
    font_attrs = [a for a in dir(theme) if a.startswith("FONT_") and not a.startswith("FONT_FAMILY") and not a.startswith("FONT_FALLBACK") and not a.startswith("FONT_MONO")]
    for attr in font_attrs:
        val = getattr(theme, attr)
        assert isinstance(val, tuple), f"{attr}={val} deveria ser tupla"
        assert len(val) >= 2, f"{attr}={val} deveria ter pelo menos familia e tamanho"
        assert isinstance(val[1], int), f"{attr}={val} tamanho deveria ser int"
    print(f"PASSOU: theme tem {len(font_attrs)} fontes validas")


# --- security ---

def test_security_validate_url():
    """validate_url deve aceitar HTTPS e rejeitar HTTP/sem schema."""
    from modules.security import validate_url
    assert validate_url("https://app.anota.ai/test"), "HTTPS deveria ser valido"
    assert not validate_url("http://app.anota.ai/test"), "HTTP nao deveria ser valido"
    assert not validate_url("ftp://something/file"), "FTP nao deveria ser valido"
    assert not validate_url("not-a-url"), "string aleatoria nao deveria ser valida"
    print("PASSOU: validate_url aceita HTTPS e rejeita outros")


def test_security_calculate_sha256():
    """calculate_sha256 deve calcular hash de um arquivo."""
    from modules.security import calculate_sha256
    import tempfile
    handle, path = tempfile.mkstemp(suffix=".txt")
    try:
        with os.fdopen(handle, "w") as f:
            f.write("hello world")
        sha = calculate_sha256(path)
        assert isinstance(sha, str), "sha256 deveria ser string"
        assert len(sha) == 64, f"sha256 deveria ter 64 chars, tem {len(sha)}"
        assert all(c in "0123456789abcdef" for c in sha), "sha256 deveria ser hex"
    finally:
        os.remove(path)
    print("PASSOU: calculate_sha256 retorna hash valido")


# --- datetime_sync ---

def test_datetime_is_admin_non_windows():
    """_is_admin deve retornar False em nao-Windows."""
    from modules.datetime_sync import _is_admin
    assert _is_admin() is False, "em Linux/Mac _is_admin deveria ser False"
    print("PASSOU: _is_admin retorna False em nao-Windows")


def test_datetime_collect_info():
    """collect_datetime_info deve retornar dict com campos esperados."""
    from modules.datetime_sync import collect_datetime_info
    from datetime import datetime, timezone
    now = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    info = collect_datetime_info(now)
    assert isinstance(info, dict)
    assert "date" in info
    assert "time" in info
    assert "timezone" in info
    assert "utc_offset" in info
    assert "daylight_saving" in info
    print("PASSOU: collect_datetime_info retorna dict com 5 campos")


# --- anota_process ---

def test_anota_name_markers():
    """_contains_anota_name deve reconhecer variacoes do nome Anota AI."""
    from modules.anota_process import _contains_anota_name
    assert _contains_anota_name("AnotaAIResponde.exe"), "deveria reconhecer AnotaAIResponde"
    assert _contains_anota_name("anotaai.exe"), "deveria reconhecer anotaai"
    assert _contains_anota_name("anota ai"), "deveria reconhecer 'anota ai'"
    assert not _contains_anota_name("chrome.exe"), "nao deveria reconhecer chrome"
    assert not _contains_anota_name("notepad.exe"), "nao deveria reconhecer notepad"
    print("PASSOU: _contains_anota_name reconhece variacoes do Anota AI")


def test_anota_normalise_name():
    """_normalise_name deve remover espacos e hifens e lowercase."""
    from modules.anota_process import _normalise_name
    assert _normalise_name("Anota AI") == "anotaai", "deveria remover espaco"
    assert _normalise_name("Anota-AI") == "anotaai", "deveria remover hifen"
    assert _normalise_name("ANOTAI") == "anotai", "deveria lowercase"
    print("PASSOU: _normalise_name normaliza corretamente")


# --- uninstaller ---

def test_uninstaller_preserved_dirs():
    """Uninstaller nao deve listar pastas preservadas como alvo."""
    from modules.temp_cleaner import ANOTA_PRESERVED_DIRS
    # Garante que logs e config estao na lista
    assert "logs" in ANOTA_PRESERVED_DIRS, "logs deveria ser preservado"
    assert "config" in ANOTA_PRESERVED_DIRS, "config deveria ser preservado"
    print("PASSOU: logs e config estao na lista de preservados")


# --- network_tools ---

def test_network_tools_import():
    """network_tools deve importar sem erro."""
    from modules import network_tools
    # Verifica que tem funções publicas
    funcs = [f for f in dir(network_tools) if not f.startswith("_") and callable(getattr(network_tools, f))]
    assert len(funcs) >= 2, f"deveria ter 2+ funções publicas, tem {len(funcs)}"
    print(f"PASSOU: network_tools importa e tem {len(funcs)} funções publicas")


# --- printer_diagnostics ---

def test_printer_diagnostics_import():
    """printer_diagnostics deve importar sem erro."""
    from modules import printer_diagnostics
    funcs = [f for f in dir(printer_diagnostics) if not f.startswith("_") and callable(getattr(printer_diagnostics, f))]
    assert len(funcs) >= 1, f"deveria ter 1+ funções publicas, tem {len(funcs)}"
    print(f"PASSOU: printer_diagnostics importa e tem {len(funcs)} funções publicas")


# --- windows_events ---

def test_windows_events_import():
    """windows_events deve importar sem erro."""
    from modules import windows_events
    funcs = [f for f in dir(windows_events) if not f.startswith("_") and callable(getattr(windows_events, f))]
    assert len(funcs) >= 1
    print(f"PASSOU: windows_events importa e tem {len(funcs)} funções publicas")


# --- windows_update ---

def test_windows_update_import():
    """windows_update deve importar sem erro."""
    from modules import windows_update
    funcs = [f for f in dir(windows_update) if not f.startswith("_") and callable(getattr(windows_update, f))]
    assert len(funcs) >= 1
    print(f"PASSOU: windows_update importa e tem {len(funcs)} funções publicas")


# --- whatsapp_status ---

def test_whatsapp_status_import():
    """whatsapp_status deve importar sem erro."""
    from modules import whatsapp_status
    funcs = [f for f in dir(whatsapp_status) if not f.startswith("_") and callable(getattr(whatsapp_status, f))]
    assert len(funcs) >= 1
    print(f"PASSOU: whatsapp_status importa e tem {len(funcs)} funções publicas")


# --- maintenance ---

def test_maintenance_import():
    """maintenance deve importar sem erro."""
    from modules import maintenance
    funcs = [f for f in dir(maintenance) if not f.startswith("_") and callable(getattr(maintenance, f))]
    assert len(funcs) >= 1
    print(f"PASSOU: maintenance importa e tem {len(funcs)} funções publicas")


# --- speedtest ---

def test_speedtest_curl_path():
    """_curl_path deve retornar string ou None."""
    from modules.speedtest import _curl_path
    path = _curl_path()
    assert path is None or isinstance(path, str), "deveria ser str ou None"
    if path:
        assert "curl" in path.lower(), f"deveria conter 'curl': {path}"
    print(f"PASSOU: _curl_path retorna {'curl em ' + path if path else 'None'}")


# --- resource_monitor ---

def test_resource_monitor_import():
    """resource_monitor deve importar sem erro."""
    try:
        from modules import resource_monitor
    except ImportError:
        print("SKIP: resource_monitor (tkinter nao disponivel)")
        return
    assert hasattr(resource_monitor, "ResourceMonitorWidget"), "deveria ter ResourceMonitorWidget"
    print("PASSOU: resource_monitor importa e tem ResourceMonitorWidget")


# --- compatibility_check ---

def test_compatibility_import():
    """compatibility_check deve importar sem erro."""
    from modules import compatibility_check
    funcs = [f for f in dir(compatibility_check) if not f.startswith("_") and callable(getattr(compatibility_check, f))]
    assert len(funcs) >= 1
    print(f"PASSOU: compatibility_check importa e tem {len(funcs)} funções publicas")


if __name__ == "__main__":
    tests = [
        test_config_values,
        test_theme_colors,
        test_theme_fonts,
        test_security_validate_url,
        test_security_calculate_sha256,
        test_datetime_is_admin_non_windows,
        test_datetime_collect_info,
        test_anota_name_markers,
        test_anota_normalise_name,
        test_uninstaller_preserved_dirs,
        test_network_tools_import,
        test_printer_diagnostics_import,
        test_windows_events_import,
        test_windows_update_import,
        test_whatsapp_status_import,
        test_maintenance_import,
        test_speedtest_curl_path,
        test_resource_monitor_import,
        test_compatibility_import,
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
            if "SKIP" in str(e):
                print(f"SKIP: {t.__name__}: {e}")
                skipped += 1
            else:
                print(f"ERRO: {t.__name__}: {type(e).__name__}: {e}")
                failed += 1
    print(f"\n=== {passed} passaram, {failed} falharam, {skipped} skipados ===")
    if failed:
        sys.exit(1)
