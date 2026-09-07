"""CLI-Tests für core/calc/triage/executor.py (P2): Exit-Codes nach
CONVENTIONS.md (0 Report/1 fachlicher Fehler/2 Eingabefehler) sowie der
CSV-Mandanten-Pfad über core/calc/parteien.py.
"""
from __future__ import annotations

import json
from pathlib import Path

from conftest import lauf, report, schreibe

EXECUTOR = Path(__file__).resolve().parents[3] / "core" / "calc" / "triage" / "executor.py"

BASIS_EINGABE = {
    "mails": [{"id": "m1", "datum": "2026-09-08", "von": "x@nirgends.example",
              "betreff": "Betreff", "text": "Text ohne Indikator."}],
    "mandanten": [{"name": "Beispiel GmbH"}],
    "bundesland": "NW",
    "heute": "2026-09-08",
}


def test_exit_0_bei_gueltiger_anfrage(tmp_path):
    eingabe = schreibe(tmp_path / "a.json", BASIS_EINGABE)
    rep = report(EXECUTOR, "--input", eingabe)
    assert rep["vorschlaege"][0]["mail_id"] == "m1"
    assert rep["meta"]["anzahl_mails"] == 1


def test_exit_1_bei_leeren_mails(tmp_path):
    eingabe = schreibe(tmp_path / "a.json", {**BASIS_EINGABE, "mails": []})
    ergebnis = lauf(EXECUTOR, "--input", eingabe)
    assert ergebnis.returncode == 1
    assert "Fehler:" in ergebnis.stderr


def test_exit_1_bei_fehlendem_bundesland(tmp_path):
    eingabe = dict(BASIS_EINGABE)
    del eingabe["bundesland"]
    pfad = schreibe(tmp_path / "a.json", eingabe)
    ergebnis = lauf(EXECUTOR, "--input", pfad)
    assert ergebnis.returncode == 1


def test_exit_1_bei_ungueltigem_heute(tmp_path):
    eingabe = schreibe(tmp_path / "a.json", {**BASIS_EINGABE, "heute": "nicht-iso"})
    ergebnis = lauf(EXECUTOR, "--input", eingabe)
    assert ergebnis.returncode == 1


def test_exit_1_bei_leerer_mandantenliste(tmp_path):
    eingabe = schreibe(tmp_path / "a.json", {**BASIS_EINGABE, "mandanten": []})
    ergebnis = lauf(EXECUTOR, "--input", eingabe)
    assert ergebnis.returncode == 1


def test_exit_2_bei_kaputtem_json(tmp_path):
    eingabe = schreibe(tmp_path / "a.json", "{kaputt")
    ergebnis = lauf(EXECUTOR, "--input", eingabe)
    assert ergebnis.returncode == 2


def test_exit_2_bei_fehlender_eingabedatei(tmp_path):
    ergebnis = lauf(EXECUTOR, "--input", str(tmp_path / "fehlt.json"))
    assert ergebnis.returncode == 2


def test_mandanten_ueber_csv_pfad(tmp_path):
    csv_pfad = tmp_path / "mandanten.csv"
    csv_pfad.write_text(
        "name;kuerzel;mandantennummer;aliasse\n"
        "Beispiel GmbH;BSP;12/345/67890;beispiel.example|BSP GmbH\n",
        encoding="utf-8")
    eingabe = schreibe(tmp_path / "a.json", {
        **BASIS_EINGABE,
        "mails": [{"id": "m1", "datum": "2026-09-08",
                  "von": "x@beispiel.example", "betreff": "Betreff", "text": "Text"}],
        "mandanten": "mandanten.csv",
    })
    rep = report(EXECUTOR, "--input", eingabe)
    assert rep["vorschlaege"][0]["mandant"] == "Beispiel GmbH"
    assert rep["vorschlaege"][0]["zuordnung_stufe"] == "domain"


def test_mandanten_csv_pfad_relativ_zur_eingabedatei(tmp_path):
    unterordner = tmp_path / "unter"
    unterordner.mkdir()
    csv_pfad = unterordner / "mandanten.csv"
    csv_pfad.write_text("name;kuerzel;mandantennummer;aliasse\nBeispiel GmbH;;;\n",
                        encoding="utf-8")
    eingabe = schreibe(unterordner / "a.json", {**BASIS_EINGABE, "mandanten": "mandanten.csv"})
    rep = report(EXECUTOR, "--input", eingabe)
    assert rep["meta"]["anzahl_mandanten"] == 1


def test_exit_1_bei_fehlender_mandanten_csv(tmp_path):
    eingabe = schreibe(tmp_path / "a.json", {**BASIS_EINGABE, "mandanten": "fehlt.csv"})
    ergebnis = lauf(EXECUTOR, "--input", eingabe)
    assert ergebnis.returncode == 1


def test_mehrdeutige_zuordnung_nennt_keinen_mandanten(tmp_path):
    # "Müller GmbH" vs. "Müller & Sohn KG", Absender nur "Mueller", Text ohne Namen:
    # Report darf keinen Mandanten als zugeordnet ausweisen, nur Kandidaten.
    eingabe = dict(BASIS_EINGABE)
    eingabe["mandanten"] = [{"name": "Müller GmbH"}, {"name": "Müller & Sohn KG"}]
    eingabe["mails"] = [{"id": "m1", "datum": "2026-09-08", "von": "Mueller <inh@example.com>",
                         "betreff": "Steuerliche Frage", "text": "Kurze Frage."}]
    rep = report(EXECUTOR, "--input", schreibe(tmp_path / "a.json", eingabe))
    v = rep["vorschlaege"][0]
    assert v["mandant"] is None
    assert v["zuordnung_stufe"] == "mehrdeutig"
    assert set(v["zuordnung_kandidaten"]) == {"Müller GmbH", "Müller & Sohn KG"}
    assert "mehrdeutig" in rep["unzugeordnet"][0]["grund"]
