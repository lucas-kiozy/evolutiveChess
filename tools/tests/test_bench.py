import importlib.util
from pathlib import Path

from luna.adapters import BACKENDS

_SCRIPT = Path(__file__).resolve().parents[1] / "bench_backends.py"


def _carregar():
    spec = importlib.util.spec_from_file_location("bench_backends", _SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_bench_smoke(capsys):
    codigo = _carregar().main(
        ["--partidas", "1", "--profundidade", "1", "--semente", "1", "--max-lances", "20"]
    )
    saida = capsys.readouterr().out
    for nome in BACKENDS:
        assert nome in saida
    assert "coincidem entre backends: sim" in saida
    assert codigo == 0
