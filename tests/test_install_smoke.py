"""Install-Smoke-Test (CI-Gate A) — prüft das *ausgelieferte* Artefakt.

Claude Code bündelt beim Install nur das `source`-Dir eines Plugins
(`plugins/tax-ops/`) in den Cache — der Repo-Root ist dort nicht vorhanden.
Dieser Test bildet genau das nach: er kopiert **ausschließlich**
`plugins/tax-ops/` in ein Temp-Verzeichnis und führt darin

  1. den Struktur-Lint aus (muss mit null Skills Exit 0 liefern), und
  2. einen deterministischen Check über die vendorte `feiertage`-API,

jeweils mit **absoluten** Pfaden und einem neutralen Arbeitsverzeichnis
(weder Repo-Root noch Plugin-Root), sodass keine CWD-Annahme durchrutschen
kann. Beweist, dass das ausgelieferte Artefakt self-contained läuft — analog
zum Install-Smoke-Test in `legal-ops-germany` (core/VENDORED.md).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN_SRC = REPO / "plugins" / "tax-ops"


def _install_cache(tmp_path: Path) -> Path:
    """Kopiert nur plugins/tax-ops/ (ohne Repo-Root) in den simulierten Cache."""
    cache = tmp_path / "install-cache" / "tax-ops"
    shutil.copytree(PLUGIN_SRC, cache,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return cache


def test_core_wird_mit_ausgeliefert(tmp_path):
    # Kernannahme (wie D14 bei legal-ops-germany): core/ liegt INNERHALB des
    # Plugins und landet im Cache.
    cache = _install_cache(tmp_path)
    assert (cache / "core" / "calc").is_dir()
    assert (cache / "core" / "verify" / "struktur_lint.py").is_file()


def test_struktur_lint_laeuft_mit_null_skills_im_cache(tmp_path):
    cache = _install_cache(tmp_path)
    neutral = tmp_path / "neutral-cwd"
    neutral.mkdir()
    ergebnis = subprocess.run(
        [sys.executable, str(cache / "core" / "verify" / "struktur_lint.py")],
        cwd=str(neutral), capture_output=True, text=True)
    assert ergebnis.returncode == 0, ergebnis.stderr
    assert "sauber" in ergebnis.stdout


def test_feiertage_api_laeuft_im_cache(tmp_path):
    """Deterministischer Check gegen die vendorte feiertage-API, ausgeführt
    aus dem reinen Plugin-Cache heraus (kein Repo-Root im Importpfad)."""
    cache = _install_cache(tmp_path)
    neutral = tmp_path / "neutral-cwd"
    neutral.mkdir(exist_ok=True)
    skript = (
        "import sys; sys.path.insert(0, str(sys.argv[1]));"
        "import datetime, feiertage;"
        "assert feiertage.ostersonntag(2026) == datetime.date(2026, 4, 5);"
        "d = datetime.date(2026, 10, 31);"
        "assert feiertage.ist_feiertag(d, 'SN').gesetzlich is True;"
        "assert feiertage.ist_feiertag(d, 'BY').gesetzlich is False;"
        "print('feiertage-check ok')"
    )
    ergebnis = subprocess.run(
        [sys.executable, "-c", skript, str(cache / "core" / "calc")],
        cwd=str(neutral), capture_output=True, text=True)
    assert ergebnis.returncode == 0, ergebnis.stderr
    assert "feiertage-check ok" in ergebnis.stdout
