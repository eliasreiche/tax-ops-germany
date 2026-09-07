"""Katalog-Provenienz (P3, CONVENTIONS.md „Nur Zeilen mit Status belegt"):
jede Zeile in indikatoren.json trägt `norm`, `quelle_url` und
`geprueft_am` — gegen die Primärquelle (Gesetzestext) nachvollziehbar,
nie freihändig ergänzt (siehe ao-fristenrechner/tests/test_katalog_provenienz.py,
gleiche Disziplin).
"""
from __future__ import annotations

import re

from triage import lade_indikatoren

_DATUM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PFLICHTFELDER = ("begriff", "kategorie", "norm", "fristart",
                  "standard_dringlichkeit", "quelle_url", "geprueft_am")
_DRINGLICHKEITEN = {"sofort", "hoch", "normal", "info"}


def test_katalog_ist_nicht_leer():
    assert lade_indikatoren()


def test_jede_zeile_traegt_alle_pflichtfelder():
    for zeile in lade_indikatoren():
        for feld in _PFLICHTFELDER:
            assert zeile.get(feld), f"{zeile.get('begriff')}: Feld '{feld}' fehlt oder leer"


def test_jede_zeile_hat_norm_und_quelle_url():
    for zeile in lade_indikatoren():
        assert zeile["norm"], f"{zeile['begriff']}: 'norm' fehlt"
        assert zeile["quelle_url"].startswith("http"), \
            f"{zeile['begriff']}: 'quelle_url' ist keine URL"
        assert _DATUM_RE.match(zeile["geprueft_am"]), \
            f"{zeile['begriff']}: 'geprueft_am' ist kein ISO-Datum"


def test_standard_dringlichkeit_ist_ein_gueltiger_wert():
    for zeile in lade_indikatoren():
        assert zeile["standard_dringlichkeit"] in _DRINGLICHKEITEN, \
            f"{zeile['begriff']}: unbekannte Dringlichkeit {zeile['standard_dringlichkeit']!r}"


def test_keine_doppelten_begriffe():
    begriffe = [z["begriff"] for z in lade_indikatoren()]
    assert len(begriffe) == len(set(begriffe)), "doppelte Begriffe im Katalog"
