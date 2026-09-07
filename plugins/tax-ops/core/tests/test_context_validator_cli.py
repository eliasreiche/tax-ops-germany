"""Tests für core/context/validator.py — CLI-Hülle um schema.py (P2).

Deckt ab: --kontext gegen beispiel-kontext/ (sauber), --datei gegen eine
einzelne Mandats-Datei, Exit-Codes (0 sauber, 1 Schema-Fehler, 2
Eingabefehler), JSON-Report-Form (`quelle: "executor"`).
"""
from __future__ import annotations

import json
import subprocess

from conftest import BEISPIEL_KONTEXT, CORE, lauf  # noqa: E402

VALIDATOR = CORE / "context" / "validator.py"


def _lauf(*args: str) -> subprocess.CompletedProcess:
    return lauf(VALIDATOR, *args)


def test_kontext_beispiel_ist_sauber_exit_0():
    res = _lauf("--kontext", str(BEISPIEL_KONTEXT))
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    assert report["ok"] is True
    assert report["fehler"] == []
    assert report["anzahl_dateien_geprueft"] == 2
    assert report["meta"]["quelle"] == "executor"


def test_einzelne_mandatsdatei_exit_0():
    datei = BEISPIEL_KONTEXT / "mandate" / "2026-001.md"
    res = _lauf("--datei", str(datei))
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    assert report["ok"] is True
    assert report["anzahl_dateien_geprueft"] == 1


def test_kaputte_mandatsdatei_exit_1(tmp_path):
    kontext = tmp_path / "kontext"
    (kontext / "mandate").mkdir(parents=True)
    (kontext / "kanzlei.md").write_text("# Test-Kanzlei\n", encoding="utf-8")
    (kontext / "mandate" / "kaputt.md").write_text(
        "---\naz: \"\"\nmandant: Test\nstand: kein-datum\nstatus: irgendwas\n---\n"
        "# Mandat\n", encoding="utf-8")
    res = _lauf("--kontext", str(kontext))
    assert res.returncode == 1, res.stderr
    report = json.loads(res.stdout)
    assert report["ok"] is False
    assert len(report["fehler"]) >= 3  # az leer, stand kein ISO, status ungueltig (+Abschnitte)
    assert "Struktur-Lint" not in res.stderr  # nicht mit dem anderen Lint verwechseln
    assert "Schema-Fehler" in res.stderr


def test_kontext_verzeichnis_fehlt_exit_2(tmp_path):
    res = _lauf("--kontext", str(tmp_path / "existiert-nicht"))
    assert res.returncode == 2
    assert "existiert-nicht" in res.stderr


def test_datei_fehlt_exit_2(tmp_path):
    res = _lauf("--datei", str(tmp_path / "fehlt.md"))
    assert res.returncode == 2


def test_kontext_und_datei_sind_exklusiv():
    res = _lauf("--kontext", str(BEISPIEL_KONTEXT), "--datei", "x.md")
    assert res.returncode != 0
    assert "not allowed" in res.stderr or "nicht erlaubt" in res.stderr or res.returncode == 2


def test_output_datei_wird_geschrieben(tmp_path):
    ziel = tmp_path / "report.json"
    res = _lauf("--kontext", str(BEISPIEL_KONTEXT), "--output", str(ziel))
    assert res.returncode == 0, res.stderr
    report = json.loads(ziel.read_text(encoding="utf-8"))
    assert report["ok"] is True
