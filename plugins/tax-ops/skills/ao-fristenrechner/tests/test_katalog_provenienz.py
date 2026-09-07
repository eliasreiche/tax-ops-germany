"""Provenienz-Test (P3, CONVENTIONS.md „Nur Zeilen mit Status belegt"):
jede Katalogzeile in fristarten.json, abgabefristen.json und
vorauszahlungstermine.json trägt `norm`, `quelle_url` und `geprueft_am` —
also gegen das Primärquellen-Dossier nachvollziehbar belegt, nie
freihändig ergänzt.
"""
from __future__ import annotations

import re

from ao_fristen import rechner as r

_DATUM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _pruefe_zeile(zeile: dict, quelle_url_fallback: str | None,
                  geprueft_am_fallback: str | None, label: str) -> None:
    norm = zeile.get("norm")
    assert norm, f"{label}: 'norm' fehlt oder ist leer"
    quelle_url = zeile.get("quelle_url", quelle_url_fallback)
    geprueft_am = zeile.get("geprueft_am", geprueft_am_fallback)
    assert quelle_url and quelle_url.startswith("http"), \
        f"{label}: 'quelle_url' fehlt oder ist keine URL"
    assert geprueft_am and _DATUM_RE.match(geprueft_am), \
        f"{label}: 'geprueft_am' fehlt oder ist kein ISO-Datum"


def test_fristarten_katalogzeilen_tragen_quelle_und_datum():
    katalog = r.lade_fristarten()
    assert katalog["fristarten"], "Katalog ist leer"
    for zeile in katalog["fristarten"]:
        _pruefe_zeile(zeile, None, None, f"fristarten.json/{zeile['id']}")


def test_abgabefristen_katalogzeilen_tragen_quelle_und_datum():
    daten = r.lade_abgabefristen()
    assert daten["veranlagungszeitraeume"], "Tabelle ist leer"
    fallback_url = daten.get("quelle_url")
    fallback_datum = daten.get("geprueft_am")
    for vz, zeile in daten["veranlagungszeitraeume"].items():
        _pruefe_zeile(zeile, fallback_url, fallback_datum, f"abgabefristen.json/VZ {vz}")
        for feld in ("nicht_beraten", "beraten", "land_forstwirt"):
            assert feld in zeile, f"VZ {vz}: Feld '{feld}' fehlt"


def test_vorauszahlungstermine_katalogzeilen_tragen_quelle_und_datum():
    daten = r.lade_vorauszahlungskatalog()
    assert daten["steuerarten"], "Katalog ist leer"
    for steuerart, zeile in daten["steuerarten"].items():
        _pruefe_zeile(zeile, None, None, f"vorauszahlungstermine.json/{steuerart}")


def test_alle_drei_kataloge_haben_stand_feld():
    for lader in (r.lade_fristarten, r.lade_abgabefristen, r.lade_vorauszahlungskatalog):
        daten = lader()
        assert daten.get("stand"), f"{lader.__name__}: 'stand' fehlt"
