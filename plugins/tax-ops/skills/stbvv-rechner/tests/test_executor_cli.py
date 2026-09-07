"""Tests für core/calc/stbvv/executor.py — CLI: JSON rein, JSON-Report raus (P2).

Deckt ab: die drei Blocktypen über die Kommandozeile, die
Schema-Beispieldateien des Skills (inkl. Sync-Check des eingecheckten
Reports), und adversariale CLI-Inputs (kaputtes JSON, fehlende Datei,
mehrere/keine Blöcke, unbekannter Key, float-Eingabe) — jeweils sauberer
Exit 2, kein Traceback.
"""
from __future__ import annotations

import json
from pathlib import Path

from conftest import CALC, lauf, report, schreibe

EXECUTOR = CALC / "stbvv" / "executor.py"
SCHEMA = Path(__file__).resolve().parents[1] / "schema"


def _report(eingabe, tmp_path: Path) -> dict:
    return report(EXECUTOR, "--input", schreibe(tmp_path / "anfrage.json", eingabe))


# --------------------------------------------------------------------------
# Erfolgsfälle je Blocktyp
# --------------------------------------------------------------------------

def test_wertgebuehr_block(tmp_path):
    r = _report({
        "wertgebuehr": {"tatbestand_id": "24-1-nr1-est-erklaerung",
                        "gegenstandswert": "50000.00", "referenzpunkt": "mittelgebuehr"},
        "auslagenpauschale": True, "umsatzsteuer": True,
    }, tmp_path)
    assert r["berechnung"]["art"] == "wertgebuehr"
    assert r["ergebnis"]["gebuehr"] == "456.40"
    assert r["ergebnis"]["brutto"] == "566.92"
    for schritt in r["rechenkette"]:
        assert schritt["quelle"] == "executor"


def test_zeitgebuehr_block(tmp_path):
    r = _report({
        "zeitgebuehr": {"stichtag": "2025-09-01", "minuten": 100, "referenzpunkt": "obergrenze"},
        "auslagenpauschale": False, "umsatzsteuer": False,
    }, tmp_path)
    assert r["berechnung"]["art"] == "zeitgebuehr"
    assert r["ergebnis"]["gebuehr"] == "287.00"
    assert r["ergebnis"]["brutto"] == "287.00"
    assert r["ergebnis"]["auslagenpauschale"] is None
    assert r["ergebnis"]["umsatzsteuer"] is None


def test_betragsrahmen_block(tmp_path):
    r = _report({
        "betragsrahmen": {"tatbestand_id": "34-2-lohnabrechnung", "einheiten": 5,
                          "referenzpunkt": "mittelgebuehr"},
        "auslagenpauschale": False, "umsatzsteuer": False,
    }, tmp_path)
    assert r["berechnung"]["art"] == "betragsrahmen_je_einheit"
    assert r["ergebnis"]["gebuehr"] == "90.00"


# --------------------------------------------------------------------------
# Schema-Beispiele (Sync mit dem eingecheckten Report)
# --------------------------------------------------------------------------

def test_beispiel_wertgebuehr_stimmt_mit_eingechecktem_report_ueberein():
    eingabe = SCHEMA / "beispiel-eingabe-wertgebuehr.json"
    erwartet = json.loads((SCHEMA / "beispiel-report.json").read_text(encoding="utf-8"))
    ergebnis = report(EXECUTOR, "--input", eingabe)
    ergebnis["meta"]["quelle_datei"] = Path(ergebnis["meta"]["quelle_datei"]).name
    erwartet["meta"]["quelle_datei"] = Path(erwartet["meta"]["quelle_datei"]).name
    assert ergebnis == erwartet


def test_beispiel_zeitgebuehr_laeuft_exit_0():
    eingabe = SCHEMA / "beispiel-eingabe-zeitgebuehr.json"
    ergebnis = lauf(EXECUTOR, "--input", eingabe)
    assert ergebnis.returncode == 0, ergebnis.stderr


def test_beispiel_betragsrahmen_laeuft_exit_0():
    eingabe = SCHEMA / "beispiel-eingabe-betragsrahmen.json"
    ergebnis = lauf(EXECUTOR, "--input", eingabe)
    assert ergebnis.returncode == 0, ergebnis.stderr


# --------------------------------------------------------------------------
# Adversariale Eingaben -> Exit 2, nie ein Traceback
# --------------------------------------------------------------------------

def test_kaputtes_json(tmp_path):
    ergebnis = lauf(EXECUTOR, "--input", schreibe(tmp_path / "kaputt.json", "{nicht json"))
    assert ergebnis.returncode == 2
    assert "Traceback" not in ergebnis.stderr
    assert ergebnis.stderr.startswith("Fehler:")


def test_fehlende_datei(tmp_path):
    ergebnis = lauf(EXECUTOR, "--input", tmp_path / "existiert-nicht.json")
    assert ergebnis.returncode == 2
    assert "Traceback" not in ergebnis.stderr


def test_kein_block(tmp_path):
    ergebnis = lauf(EXECUTOR, "--input", schreibe(tmp_path / "leer.json", {}))
    assert ergebnis.returncode == 1


def test_zwei_bloecke_gleichzeitig(tmp_path):
    ergebnis = lauf(EXECUTOR, "--input", schreibe(tmp_path / "zwei.json", {
        "wertgebuehr": {"tatbestand_id": "24-1-nr1-est-erklaerung",
                        "gegenstandswert": "50000", "referenzpunkt": "mittelgebuehr"},
        "zeitgebuehr": {"stichtag": "2025-07-01", "minuten": 15, "referenzpunkt": "untergrenze"},
    }))
    assert ergebnis.returncode == 1


def test_unbekannter_key_oberste_ebene(tmp_path):
    ergebnis = lauf(EXECUTOR, "--input", schreibe(tmp_path / "tippfehler.json", {
        "wertgebuehr": {"tatbestand_id": "24-1-nr1-est-erklaerung",
                        "gegenstandswert": "50000", "referenzpunkt": "mittelgebuehr"},
        "auslagenpauchale": True,
    }))
    assert ergebnis.returncode == 1
    assert "auslagenpauchale" in ergebnis.stderr


def test_float_gegenstandswert_wird_abgelehnt(tmp_path):
    ergebnis = lauf(EXECUTOR, "--input", schreibe(tmp_path / "float.json", {
        "wertgebuehr": {"tatbestand_id": "24-1-nr1-est-erklaerung",
                        "gegenstandswert": 50000.0, "referenzpunkt": "mittelgebuehr"},
    }))
    assert ergebnis.returncode == 1
    assert "float" in ergebnis.stderr


def test_zeitgebuehr_vor_stichtag_exit_1(tmp_path):
    ergebnis = lauf(EXECUTOR, "--input", schreibe(tmp_path / "alt.json", {
        "zeitgebuehr": {"stichtag": "2024-01-01", "minuten": 20, "referenzpunkt": "mittelgebuehr"},
    }))
    assert ergebnis.returncode == 1
    assert "2025-07-01" in ergebnis.stderr
