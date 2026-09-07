"""Tests für core/context/schema.py — reine Schema-Prüf-Logik (P3/P4).

Deckt ab: Frontmatter-Parsing (inkl. explizitem YAML-null), Pflichtfelder,
ISO-Datumsformate, status-Enum, Pflicht-Abschnitte, Verweis-Integrität
(Warnung) sowie das ganze `beispiel-kontext/`-Fixture als "gut"-Referenz.
"""
from __future__ import annotations


import pytest

from conftest import BEISPIEL_KONTEXT  # noqa: E402

from context import schema  # noqa: E402


# --------------------------------------------------------------------------
# Frontmatter-Parsing
# --------------------------------------------------------------------------

def test_lade_frontmatter_liest_werte_und_zeilen():
    fm = schema.lade_frontmatter(
        '---\naz: "2026-001"\nmandant: Test\nmandatsende: null\nstand: 2026-01-01\n---\n# x\n')
    assert fm["az"] == ("2026-001", 2)
    assert fm["mandant"] == ("Test", 3)
    assert fm["mandatsende"] == (None, 4)
    assert fm["stand"] == ("2026-01-01", 5)


def test_lade_frontmatter_ohne_block():
    assert schema.lade_frontmatter("# kein Frontmatter\n") is None


def test_lade_frontmatter_tilde_ist_null():
    fm = schema.lade_frontmatter("---\nstreitwert: ~\n---\n# x\n")
    assert fm["streitwert"] == (None, 2)


# --------------------------------------------------------------------------
# Mandats-Schema — gut
# --------------------------------------------------------------------------

MANDAT_GUT = """---
az: "2026-001"
mandant: "Beispiel GmbH"
gegenseite: "Muster AG"
stand: 2026-07-01
mandatsende: null
streitwert: 12500.00
status: aktiv
---

# Mandat 2026-001

## Parteien

| Rolle | Name | Vertreter |
|---|---|---|
| Mandant | Beispiel GmbH | RA X |

## Kommunikation

- 2026-06-20 — Test — kein Link hier

## Letzter Schritt

Text.

## Nächste Frist

Verweis: `abc123@fristenrechner.legal-ops`
"""


def test_mandat_gut_ist_fehlerfrei():
    fehler, warnungen = schema.pruefe_mandat_text(MANDAT_GUT, "test.md")
    assert fehler == []
    assert warnungen == []


def test_mandat_ohne_frontmatter():
    fehler, warnungen = schema.pruefe_mandat_text("# nur Text\n", "test.md")
    assert any("kein Frontmatter-Block" in f for f in fehler)


@pytest.mark.parametrize("feld", ["az", "mandant", "stand"])
def test_mandat_pflichtfeld_fehlt(feld):
    text = MANDAT_GUT.replace(f"{feld}:", f"_{feld}:", 1)
    fehler, _ = schema.pruefe_mandat_text(text, "test.md")
    assert any(f"Pflichtfeld '{feld}'" in f for f in fehler), fehler


def test_mandat_pflichtfeld_leer():
    text = MANDAT_GUT.replace('az: "2026-001"', 'az: ""')
    fehler, _ = schema.pruefe_mandat_text(text, "test.md")
    assert any("Pflichtfeld 'az'" in f for f in fehler)


def test_mandat_stand_kein_iso_datum():
    text = MANDAT_GUT.replace("stand: 2026-07-01", "stand: 01.07.2026")
    fehler, _ = schema.pruefe_mandat_text(text, "test.md")
    assert any("'stand' ist kein ISO-Datum" in f for f in fehler)


def test_mandat_mandatsende_weder_datum_noch_null():
    text = MANDAT_GUT.replace("mandatsende: null", "mandatsende: irgendwann")
    fehler, _ = schema.pruefe_mandat_text(text, "test.md")
    assert any("'mandatsende' ist weder ISO-Datum noch null" in f for f in fehler)


def test_mandat_mandatsende_gueltiges_datum_ist_ok():
    text = MANDAT_GUT.replace("mandatsende: null", "mandatsende: 2026-03-31")
    fehler, _ = schema.pruefe_mandat_text(text, "test.md")
    assert fehler == []


def test_mandat_streitwert_weder_zahl_noch_null():
    text = MANDAT_GUT.replace("streitwert: 12500.00", "streitwert: viel")
    fehler, _ = schema.pruefe_mandat_text(text, "test.md")
    assert any("'streitwert' ist weder Zahl noch null" in f for f in fehler)


def test_mandat_status_ungueltiger_wert():
    text = MANDAT_GUT.replace("status: aktiv", "status: irgendwas")
    fehler, _ = schema.pruefe_mandat_text(text, "test.md")
    assert any("'status' muss einer von" in f for f in fehler)


@pytest.mark.parametrize("status", ["aktiv", "ruhend", "beendet"])
def test_mandat_status_gueltige_werte(status):
    text = MANDAT_GUT.replace("status: aktiv", f"status: {status}")
    fehler, _ = schema.pruefe_mandat_text(text, "test.md")
    assert fehler == []


@pytest.mark.parametrize("abschnitt", list(schema.ABSCHNITTE_MANDAT))
def test_mandat_pflicht_abschnitt_fehlt(abschnitt):
    text = MANDAT_GUT.replace(abschnitt, "## Umbenannter Abschnitt")
    fehler, _ = schema.pruefe_mandat_text(text, "test.md")
    assert any(f"Pflicht-Abschnitt '{abschnitt}' fehlt" in f for f in fehler), fehler


def test_mandat_ohne_empfohlene_felder_nur_warnung():
    text = MANDAT_GUT.replace('gegenseite: "Muster AG"\n', "")
    fehler, warnungen = schema.pruefe_mandat_text(text, "test.md")
    assert fehler == []
    assert any("empfohlenes Feld 'gegenseite' fehlt" in w for w in warnungen)


def test_mandat_naechste_frist_ohne_uid_und_ohne_erledigt_hinweis_ist_warnung():
    text = MANDAT_GUT.replace(
        "Verweis: `abc123@fristenrechner.legal-ops`", "Muss noch geklärt werden.")
    fehler, warnungen = schema.pruefe_mandat_text(text, "test.md")
    assert fehler == []
    assert any("keinen erkennbaren iCal-UID-Verweis" in w for w in warnungen)


def test_mandat_naechste_frist_keine_offene_frist_ist_ok():
    text = MANDAT_GUT.replace(
        "Verweis: `abc123@fristenrechner.legal-ops`", "Keine offene Frist.")
    _, warnungen = schema.pruefe_mandat_text(text, "test.md")
    assert warnungen == []


# --------------------------------------------------------------------------
# Datei-Ebene: Verweis-Integrität (Warnung)
# --------------------------------------------------------------------------

def test_verweis_integritaet_fehlendes_ziel_ist_warnung(tmp_path):
    (tmp_path / "posteingang").mkdir()
    text = MANDAT_GUT.replace(
        "- 2026-06-20 — Test — kein Link hier",
        "- 2026-06-20 — Test — [Datei](posteingang/fehlt.md)")
    datei = tmp_path / "mandat.md"
    datei.write_text(text, encoding="utf-8")
    fehler, warnungen = schema.pruefe_mandat_datei(datei)
    assert fehler == []
    assert any("Verweis-Ziel nicht gefunden" in w for w in warnungen)


def test_verweis_integritaet_vorhandenes_ziel_ist_sauber(tmp_path):
    (tmp_path / "posteingang").mkdir()
    (tmp_path / "posteingang" / "beleg.md").write_text("x", encoding="utf-8")
    text = MANDAT_GUT.replace(
        "- 2026-06-20 — Test — kein Link hier",
        "- 2026-06-20 — Test — [Datei](posteingang/beleg.md)")
    datei = tmp_path / "mandat.md"
    datei.write_text(text, encoding="utf-8")
    fehler, warnungen = schema.pruefe_mandat_datei(datei)
    assert fehler == []
    assert warnungen == []


def test_mandat_datei_nicht_gefunden(tmp_path):
    fehler, warnungen = schema.pruefe_mandat_datei(tmp_path / "fehlt.md")
    assert any("Datei nicht gefunden" in f for f in fehler)
    assert warnungen == []


# --------------------------------------------------------------------------
# kanzlei.md
# --------------------------------------------------------------------------

def test_kanzlei_datei_fehlt_ist_fehler(tmp_path):
    fehler, _ = schema.pruefe_kanzlei_datei(tmp_path / "kanzlei.md")
    assert any("Pflichtdatei fehlt" in f for f in fehler)


def test_kanzlei_datei_ohne_h1_ist_nur_warnung(tmp_path):
    datei = tmp_path / "kanzlei.md"
    datei.write_text("kein Titel hier\n", encoding="utf-8")
    fehler, warnungen = schema.pruefe_kanzlei_datei(datei)
    assert fehler == []
    assert any("keine H1-Überschrift" in w for w in warnungen)


def test_kanzlei_datei_mit_h1_ist_sauber(tmp_path):
    datei = tmp_path / "kanzlei.md"
    datei.write_text("# Kanzlei X\n", encoding="utf-8")
    fehler, warnungen = schema.pruefe_kanzlei_datei(datei)
    assert fehler == []
    assert warnungen == []


# --------------------------------------------------------------------------
# Ganzes Verzeichnis — beispiel-kontext/ als "gut"-Referenz
# --------------------------------------------------------------------------

def test_beispiel_kontext_ist_fehlerfrei():
    fehler, warnungen, anzahl = schema.pruefe_kontext_verzeichnis(BEISPIEL_KONTEXT)
    assert fehler == [], fehler
    assert warnungen == [], warnungen
    assert anzahl == 2


def test_pruefe_kontext_verzeichnis_ohne_kanzlei_md(tmp_path):
    (tmp_path / "mandate").mkdir()
    fehler, warnungen, anzahl = schema.pruefe_kontext_verzeichnis(tmp_path)
    assert any("Pflichtdatei fehlt" in f for f in fehler)
    assert anzahl == 0


def test_pruefe_kontext_verzeichnis_ohne_mandate_ordner_ist_warnung(tmp_path):
    (tmp_path / "kanzlei.md").write_text("# X\n", encoding="utf-8")
    fehler, warnungen, anzahl = schema.pruefe_kontext_verzeichnis(tmp_path)
    assert fehler == []
    assert any("Ordner fehlt" in w for w in warnungen)
    assert anzahl == 0


# --------------------------------------------------------------------------
# lese_mandate (für den Retention-Executor)
# --------------------------------------------------------------------------

def test_lese_mandate_liefert_frontmatter_je_datei():
    mandate = schema.lese_mandate(BEISPIEL_KONTEXT)
    assert len(mandate) == 2
    azs = sorted(fm["az"][0] for _, fm in mandate)
    assert azs == ["2026-001", "2026-002"]


def test_lese_mandate_ohne_mandate_ordner(tmp_path):
    assert schema.lese_mandate(tmp_path) == []


def test_lese_mandate_ueberspringt_datei_ohne_frontmatter(tmp_path):
    mandate_dir = tmp_path / "mandate"
    mandate_dir.mkdir()
    (mandate_dir / "kaputt.md").write_text("kein frontmatter\n", encoding="utf-8")
    assert schema.lese_mandate(tmp_path) == []
