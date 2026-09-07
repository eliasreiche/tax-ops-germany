"""Fristindikatoren (Baustein 2): jede Kategorie triggert per Substring-
Suche, längster/spezifischerer Begriff verdrängt einen generischeren aus
einer ANDEREN Kategorie (Vorauszahlungsbescheid darf nicht zusätzlich als
generischer Steuerbescheid einsortiert werden), und die
Bescheiddatum-Extraktion (Baustein 3) für den Ambiguitätsfall.
"""
from __future__ import annotations

import pytest

from triage import erkenne_indikatoren, extrahiere_bescheiddatum, lade_indikatoren

PROBEN = {
    "bescheid_einspruch": "Anbei erhalten Sie den Steuerbescheid.",
    "pruefungsanordnung": "Hiermit ergeht die Prüfungsanordnung.",
    "anhoerung": "Wir geben Ihnen Gelegenheit zur Stellungnahme.",
    "mahnung_vollstreckung": "Dies ist eine Mahnung.",
    "vorauszahlungsbescheid": "Der Vorauszahlungsbescheid liegt bei.",
    "erinnerung_schaetzung": "Wir drohen eine Schätzungsandrohung an.",
    "fragebogen": "Bitte füllen Sie den Fragebogen aus.",
    "lohn_sozialversicherung_pruefung": "Es folgt eine Sozialversicherungsprüfung.",
    "ust_sonderpruefung_nachschau": "Es erfolgt eine Umsatzsteuer-Nachschau.",
}


@pytest.mark.parametrize("kategorie,text", sorted(PROBEN.items()))
def test_jede_kategorie_triggert_einmal(kategorie, text):
    treffer = erkenne_indikatoren("", text)
    kategorien = [t["kategorie"] for t in treffer]
    assert kategorie in kategorien, f"{kategorie} nicht erkannt in: {text!r}"


def test_alle_katalog_kategorien_sind_in_proben_abgedeckt():
    katalog_kategorien = {z["kategorie"] for z in lade_indikatoren()}
    assert katalog_kategorien == set(PROBEN), (
        "PROBEN in diesem Test deckt nicht (mehr) exakt alle Katalog-Kategorien ab")


def test_vorauszahlungsbescheid_triggert_nicht_zusaetzlich_bescheid_einspruch():
    treffer = erkenne_indikatoren(
        "Vorauszahlungsbescheid", "Vorauszahlungsbescheid vom 06.09.2026 liegt bei.")
    kategorien = [t["kategorie"] for t in treffer]
    assert kategorien == ["vorauszahlungsbescheid"]


def test_generischer_bescheid_greift_ohne_spezifischeren_begriff():
    treffer = erkenne_indikatoren("Bescheid", "Der Bescheid liegt bei.")
    kategorien = [t["kategorie"] for t in treffer]
    assert kategorien == ["bescheid_einspruch"]


def test_kein_indikator_ohne_treffer():
    assert erkenne_indikatoren("Allgemeine Anfrage", "Wir hätten gerne ein Angebot.") == []


# --------------------------------------------------------------------------
# Bescheiddatum-Extraktion (Baustein 3) — Ambiguitätsfall
# --------------------------------------------------------------------------

def test_bescheiddatum_eindeutig():
    datum, mehrdeutig = extrahiere_bescheiddatum("Bescheid vom 03.02.2026.")
    assert datum == "2026-02-03"
    assert mehrdeutig is False


def test_bescheiddatum_mehrdeutig_bei_zwei_label_stellen():
    datum, mehrdeutig = extrahiere_bescheiddatum(
        "Bescheid vom 01.09.2026, alternativ Datum 03.09.2026 laut Poststempel.")
    assert datum is None
    assert mehrdeutig is True


def test_bescheiddatum_kein_label_ist_kein_treffer_und_nicht_mehrdeutig():
    datum, mehrdeutig = extrahiere_bescheiddatum("Ohne jede Datumsnennung im Text.")
    assert datum is None
    assert mehrdeutig is False
