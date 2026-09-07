"""Beispiel-Sync-Test (P4): schema/beispiel-report.json muss exakt dem
entsprechen, was der Executor aktuell aus schema/beispiel-eingabe.json
erzeugt — dieselbe Disziplin wie bei email-akten-zuordnung in
legal-ops-germany (core/VENDORED.md).
"""
from __future__ import annotations

import json
from pathlib import Path

from conftest import neutralisiere, report

SKILL_DIR = Path(__file__).resolve().parents[1]
EXECUTOR = SKILL_DIR.parents[1] / "core" / "calc" / "triage" / "executor.py"
SCHEMA = SKILL_DIR / "schema"

# 'quelle_datei' hängt vom Aufrufpfad ab (absolut/relativ je nach cwd).
PFADFELDER = ("quelle_datei",)


def test_beispiel_report_ist_aktuell():
    frisch = neutralisiere(
        report(EXECUTOR, "--input", SCHEMA / "beispiel-eingabe.json"), PFADFELDER)
    checked_in = neutralisiere(
        json.loads((SCHEMA / "beispiel-report.json").read_text(encoding="utf-8")),
        PFADFELDER)
    assert frisch == checked_in, (
        "schema/beispiel-report.json ist veraltet — neu erzeugen mit:\n"
        f"python3 {EXECUTOR} --input {SCHEMA / 'beispiel-eingabe.json'} "
        f"--output {SCHEMA / 'beispiel-report.json'}")


def test_beispiel_eingabe_ist_fiktiv():
    inhalt = (SCHEMA / "beispiel-eingabe.json").read_text(encoding="utf-8")
    assert ".example" in inhalt, "keine erkennbare .example-Domain (fiktiv?)"
    for verboten in ("@gmail.com", "@gmx.de", "@web.de"):
        assert verboten not in inhalt
