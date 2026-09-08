"""Regex-Netz von tax-ops-feedback: Mandantenmuster werden erkannt, saubere Reports nicht."""
import importlib.util
import subprocess
import sys
from pathlib import Path

SKRIPT = Path(__file__).resolve().parents[1] / "pruefe_report.py"
spec = importlib.util.spec_from_file_location("pruefe_report", SKRIPT)
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)


def test_erkennt_mandantenmuster():
    text = ("Mandant: Backstube Sonnenschein GmbH\nSteuernummer 12/345/67890\n"
            "info@backstube.example, Tel. 0221 123456, Herr Meier, Az: 4711/26")
    arten = {name for _, name, _ in pr.pruefe(text)}
    assert {"Firma", "Steuernummer", "E-Mail", "Telefon", "Anrede/Name", "Aktenzeichen"} <= arten


def test_sauberer_report_ohne_treffer():
    text = ("Skill: ao-fristenrechner\naufgabe_zur_post: 2026-02-03, bundesland: NW\n"
            "Ergebnis: 2026-03-09, erwartet: 2026-03-06\nAn: elias@law-flow.de\n"
            "Mandant: [Mandant], Betrag: [Betrag]")
    assert pr.pruefe(text) == []


def test_cli_exit_codes(tmp_path):
    schmutzig = tmp_path / "s.md"; schmutzig.write_text("Steuernummer 12/345/67890")
    sauber = tmp_path / "c.md"; sauber.write_text("Skill: stbvv-rechner, gegenstandswert: 50000")
    assert subprocess.run([sys.executable, SKRIPT, "--datei", schmutzig]).returncode == 1
    assert subprocess.run([sys.executable, SKRIPT, "--datei", sauber]).returncode == 0
    assert subprocess.run([sys.executable, SKRIPT, "--datei", tmp_path / "fehlt.md"]).returncode == 2
