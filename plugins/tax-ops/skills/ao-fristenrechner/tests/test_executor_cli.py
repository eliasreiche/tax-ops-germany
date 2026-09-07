"""CLI-Tests für core/calc/ao_fristen/executor.py (P2).

Deckt ab: Exit-Codes (0 Report/1 Eingabefehler/2 nicht abgedeckt — abweichend
von der allgemeinen Executor-Konvention in CONVENTIONS.md, siehe SKILL.md
schema/README.md „Exit-Codes"), Ablehnung nicht abgedeckter Eingaben je
Modus, und dass jeder Modus einen validen Report mit `kalender_termine`
liefert.
"""
from __future__ import annotations

import json
from pathlib import Path

from conftest import lauf, report, schreibe

EXECUTOR = Path(__file__).resolve().parents[3] / "core" / "calc" / "ao_fristen" / "executor.py"
SCHEMA = Path(__file__).resolve().parents[1] / "schema"


def test_exit_0_bei_gueltiger_einspruch_anfrage(tmp_path):
    eingabe = schreibe(tmp_path / "a.json", {
        "modus": "einspruch", "bundesland": "NW", "bekanntgabe_datum": "2026-01-15"})
    rep = report(EXECUTOR, "--input", eingabe)
    assert rep["fristende"] == "2026-02-16"
    assert rep["quelle"] == "executor"
    assert rep["kalender_termine"][0]["datum"] == rep["fristende"]


def test_exit_1_bei_fehlendem_pflichtfeld(tmp_path):
    eingabe = schreibe(tmp_path / "a.json", {"modus": "einspruch", "bundesland": "NW"})
    ergebnis = lauf(EXECUTOR, "--input", eingabe)
    assert ergebnis.returncode == 1
    assert "Fehler:" in ergebnis.stderr


def test_exit_1_bei_unbekanntem_modus(tmp_path):
    eingabe = schreibe(tmp_path / "a.json", {"modus": "unbekannt"})
    ergebnis = lauf(EXECUTOR, "--input", eingabe)
    assert ergebnis.returncode == 1


def test_exit_1_bei_kaputtem_json(tmp_path):
    eingabe = schreibe(tmp_path / "a.json", "{kaputt")
    ergebnis = lauf(EXECUTOR, "--input", eingabe)
    assert ergebnis.returncode == 1


def test_exit_1_bei_fehlender_eingabedatei(tmp_path):
    ergebnis = lauf(EXECUTOR, "--input", str(tmp_path / "fehlt.json"))
    assert ergebnis.returncode == 1


def test_exit_2_bei_aufgabe_zur_post_vor_2025(tmp_path):
    eingabe = schreibe(tmp_path / "a.json", {
        "modus": "einspruch", "bundesland": "NW",
        "aufgabe_zur_post_datum": "2024-12-31"})
    ergebnis = lauf(EXECUTOR, "--input", eingabe)
    assert ergebnis.returncode == 2
    assert "Nicht abgedeckt:" in ergebnis.stderr


def test_exit_2_bei_land_forstwirt_ab_vz2025(tmp_path):
    eingabe = schreibe(tmp_path / "a.json", {
        "modus": "abgabefrist", "veranlagungszeitraum": 2025,
        "gruppe": "land_forstwirt", "bundesland": "NW"})
    ergebnis = lauf(EXECUTOR, "--input", eingabe)
    assert ergebnis.returncode == 2


def test_alle_modi_liefern_kalender_termine(tmp_path):
    faelle = [
        {"modus": "einspruch", "bundesland": "NW", "bekanntgabe_datum": "2026-01-15"},
        {"modus": "abgabefrist", "veranlagungszeitraum": 2024, "gruppe": "beraten",
         "bundesland": "NW"},
        {"modus": "vorauszahlung", "jahr": 2026, "steuerart": "est", "bundesland": "NW"},
        {"modus": "verspaetungszuschlag", "festgesetzte_steuer": 1000,
         "abgabedatum": "2026-10-15", "fristende": "2026-07-31"},
    ]
    for i, fall in enumerate(faelle):
        eingabe = schreibe(tmp_path / f"fall{i}.json", fall)
        rep = report(EXECUTOR, "--input", eingabe)
        assert rep["quelle"] == "executor"
        assert isinstance(rep["kalender_termine"], list) and rep["kalender_termine"]
        assert all("quelle" in s and s["quelle"] == "executor" for s in rep["rechenkette"])


def test_output_flag_schreibt_datei(tmp_path):
    eingabe = schreibe(tmp_path / "a.json", {
        "modus": "einspruch", "bundesland": "NW", "bekanntgabe_datum": "2026-01-15"})
    ausgabe = tmp_path / "report.json"
    ergebnis = lauf(EXECUTOR, "--input", eingabe, "--output", str(ausgabe))
    assert ergebnis.returncode == 0
    assert ausgabe.is_file()


# --------------------------------------------------------------------------
# Schema-Beispieldateien (Golden Files) bleiben synchron
# --------------------------------------------------------------------------

def _vergleiche_golden(name: str) -> None:
    ergebnis = lauf(EXECUTOR, "--input", SCHEMA / f"beispiel-eingabe-{name}.json")
    assert ergebnis.returncode == 0, ergebnis.stderr
    erzeugt = json.loads(ergebnis.stdout)
    gespeichert = json.loads(
        (SCHEMA / f"beispiel-report-{name}.json").read_text(encoding="utf-8"))
    # quelle_datei ist pfadabhängig (absolut vs. relativ je nach Aufrufort) —
    # für den Vergleich neutralisieren, alles andere muss exakt übereinstimmen.
    erzeugt["meta"].pop("quelle_datei")
    gespeichert["meta"].pop("quelle_datei")
    assert erzeugt == gespeichert


def test_golden_beispiel_einspruch_synchron():
    _vergleiche_golden("einspruch")


def test_golden_beispiel_abgabefrist_synchron():
    _vergleiche_golden("abgabefrist")


def test_golden_beispiel_vorauszahlung_synchron():
    _vergleiche_golden("vorauszahlung")


def test_golden_beispiel_verspaetungszuschlag_synchron():
    _vergleiche_golden("verspaetungszuschlag")
