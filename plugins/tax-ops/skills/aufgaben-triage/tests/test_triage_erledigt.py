"""Erledigt-Vorschlag (Baustein 5): offene Aufgabe gilt als vermutlich
erledigt, wenn eine gesendete Mail an denselben (zugeordneten) Mandanten
per thread_id/in_reply_to oder normalisiertem Betreff nach `angelegt`
verknüpft ist — nur Vorschlag mit Beleg, kein automatisches Austragen.
"""
from __future__ import annotations

from triage import Mandant, finde_erledigt_vorschlaege

MANDANTEN = [
    Mandant(name="Backstube Sonnenschein GmbH", aliasse=["backstube.example"]),
    Mandant(name="Muster-Handel KG", aliasse=["muster-handel.example"]),
]


def test_positiv_ueber_thread_id():
    aufgaben = [{"id": "a1", "mandant": "Backstube Sonnenschein GmbH",
                "titel": "Lohnunterlagen anfordern", "angelegt": "2026-08-01",
                "thread_id": "thread-1"}]
    gesendet = [{"datum": "2026-08-05", "an": "p@backstube.example",
                "betreff": "AW: Lohnunterlagen anfordern", "thread_id": "thread-1"}]
    vorschlaege = finde_erledigt_vorschlaege(aufgaben, gesendet, MANDANTEN)
    assert len(vorschlaege) == 1
    assert vorschlaege[0]["match_art"] == "thread_id"
    assert vorschlaege[0]["aufgabe_id"] == "a1"


def test_positiv_ueber_normalisierten_betreff():
    aufgaben = [{"id": "a2", "mandant": "Backstube Sonnenschein GmbH",
                "titel": "Unterlagen Y", "angelegt": "2026-08-01",
                "betreff": "Unterlagen Y"}]
    gesendet = [{"datum": "2026-08-06", "an": "p@backstube.example",
                "betreff": "Re: unterlagen y"}]
    vorschlaege = finde_erledigt_vorschlaege(aufgaben, gesendet, MANDANTEN)
    assert len(vorschlaege) == 1
    assert vorschlaege[0]["match_art"] == "betreff_normalisiert"


def test_negativ_antwort_vor_angelegt():
    aufgaben = [{"id": "a3", "mandant": "Backstube Sonnenschein GmbH",
                "titel": "X", "angelegt": "2026-08-10", "thread_id": "thread-3"}]
    gesendet = [{"datum": "2026-08-05", "an": "p@backstube.example",
                "betreff": "AW: X", "thread_id": "thread-3"}]
    assert finde_erledigt_vorschlaege(aufgaben, gesendet, MANDANTEN) == []


def test_negativ_anderer_mandant():
    aufgaben = [{"id": "a4", "mandant": "Muster-Handel KG",
                "titel": "Z", "angelegt": "2026-08-01", "thread_id": "thread-4"}]
    # gesendet geht an die Backstube, nicht an Muster-Handel -> kein Beleg
    # fuer DIESE Aufgabe, obwohl thread_id zufaellig gleich ist.
    gesendet = [{"datum": "2026-08-05", "an": "p@backstube.example",
                "betreff": "AW: Z", "thread_id": "thread-4"}]
    assert finde_erledigt_vorschlaege(aufgaben, gesendet, MANDANTEN) == []


def test_kein_beleg_ohne_uebereinstimmung():
    aufgaben = [{"id": "a5", "mandant": "Backstube Sonnenschein GmbH",
                "titel": "Ohne Bezug", "angelegt": "2026-08-01"}]
    gesendet = [{"datum": "2026-08-05", "an": "p@backstube.example",
                "betreff": "Voellig anderer Betreff"}]
    assert finde_erledigt_vorschlaege(aufgaben, gesendet, MANDANTEN) == []
