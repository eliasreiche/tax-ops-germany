"""Tests für core/calc/ao_fristen/kalender_executor.py (P2/P3).

Deckt ab: Ablehnung von Nicht-Executor-Reports, ein VEVENT/eine CSV-Zeile
je Eintrag in `kalender_termine`, und die Kern-Eigenschaft „Re-Export nur
bei Korrektur": zweimal exportieren ergibt byte-identische Dateien; eine
geänderte Eingabe ändert die UID.
"""
from __future__ import annotations

from pathlib import Path

from conftest import lauf, schreibe

EXECUTOR = Path(__file__).resolve().parents[3] / "core" / "calc" / "ao_fristen" / "executor.py"
KALENDER = (Path(__file__).resolve().parents[3] / "core" / "calc" / "ao_fristen"
           / "kalender_executor.py")


def _report(tmp_path: Path, name: str, eingabe: dict) -> Path:
    eingabe_pfad = schreibe(tmp_path / f"{name}-eingabe.json", eingabe)
    report_pfad = tmp_path / f"{name}-report.json"
    ergebnis = lauf(EXECUTOR, "--input", eingabe_pfad, "--output", report_pfad)
    assert ergebnis.returncode == 0, ergebnis.stderr
    return report_pfad


def test_lehnt_nicht_executor_report_ab(tmp_path):
    kaputt = schreibe(tmp_path / "kaputt.json", {"quelle": "modell", "kalender_termine": []})
    ergebnis = lauf(KALENDER, "--report", kaputt, "--format", "ics")
    assert ergebnis.returncode == 2
    assert "Fehler:" in ergebnis.stderr


def test_lehnt_report_ohne_kalender_termine_ab(tmp_path):
    kaputt = schreibe(tmp_path / "kaputt.json", {"quelle": "executor"})
    ergebnis = lauf(KALENDER, "--report", kaputt, "--format", "ics")
    assert ergebnis.returncode == 2


def test_ein_vevent_je_kalender_termin(tmp_path):
    rep = _report(tmp_path, "vz", {
        "modus": "vorauszahlung", "jahr": 2026, "steuerart": "est", "bundesland": "NW"})
    ergebnis = lauf(KALENDER, "--report", rep, "--format", "ics")
    assert ergebnis.returncode == 0
    assert ergebnis.stdout.count("BEGIN:VEVENT") == 4
    assert ergebnis.stdout.count("END:VEVENT") == 4


def test_csv_eine_zeile_je_termin(tmp_path):
    rep = _report(tmp_path, "vz", {
        "modus": "vorauszahlung", "jahr": 2026, "steuerart": "gewst", "bundesland": "NW"})
    ergebnis = lauf(KALENDER, "--report", rep, "--format", "csv")
    assert ergebnis.returncode == 0
    zeilen = ergebnis.stdout.strip("\r\n").splitlines()
    assert len(zeilen) == 5  # Kopf + 4 Termine


def test_export_ist_idempotent_zweimal_identisch(tmp_path):
    rep = _report(tmp_path, "einspruch", {
        "modus": "einspruch", "bundesland": "NW", "bekanntgabe_datum": "2026-01-15"})
    a = lauf(KALENDER, "--report", rep, "--format", "ics", "--aktenzeichen", "2026-042")
    b = lauf(KALENDER, "--report", rep, "--format", "ics", "--aktenzeichen", "2026-042")
    assert a.returncode == b.returncode == 0
    assert a.stdout == b.stdout

    c = lauf(KALENDER, "--report", rep, "--format", "csv", "--aktenzeichen", "2026-042")
    d = lauf(KALENDER, "--report", rep, "--format", "csv", "--aktenzeichen", "2026-042")
    assert c.stdout == d.stdout


def test_korrigierte_eingabe_aendert_uid(tmp_path):
    rep1 = _report(tmp_path, "e1", {
        "modus": "einspruch", "bundesland": "NW", "bekanntgabe_datum": "2026-01-15"})
    rep2 = _report(tmp_path, "e2", {
        "modus": "einspruch", "bundesland": "NW", "bekanntgabe_datum": "2026-01-16"})
    a = lauf(KALENDER, "--report", rep1, "--format", "csv")
    b = lauf(KALENDER, "--report", rep2, "--format", "csv")
    uid_a = a.stdout.strip().splitlines()[1].split(";")[-2]
    uid_b = b.stdout.strip().splitlines()[1].split(";")[-2]
    assert uid_a != uid_b


def test_format_beide_verlangt_output_dir(tmp_path):
    rep = _report(tmp_path, "e", {
        "modus": "einspruch", "bundesland": "NW", "bekanntgabe_datum": "2026-01-15"})
    ergebnis = lauf(KALENDER, "--report", rep, "--format", "beide")
    assert ergebnis.returncode == 2


def test_format_beide_schreibt_zwei_dateien(tmp_path):
    rep = _report(tmp_path, "e", {
        "modus": "einspruch", "bundesland": "NW", "bekanntgabe_datum": "2026-01-15"})
    zielordner = tmp_path / "export"
    ergebnis = lauf(KALENDER, "--report", rep, "--format", "beide",
                    "--output-dir", zielordner)
    assert ergebnis.returncode == 0
    dateien = list(zielordner.iterdir())
    assert len(dateien) == 2
    assert {p.suffix for p in dateien} == {".ics", ".csv"}
