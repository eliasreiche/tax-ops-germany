"""Bescheiddatum -> Fälligkeit (Baustein 3): der Rechner reicht das
extrahierte Bescheiddatum unverändert an `core/calc/ao_fristen` weiter
(Wochenendfall aus dem ao-fristenrechner-Beispiel, SKILL.md „Beispiel 1")
und übernimmt kein eigenes AO-Fristrecht.
"""
from __future__ import annotations

import datetime

from ao_fristen.rechner import berechne_einspruchsfrist
from triage import extrahiere_bescheiddatum
from triage.rechner import berechne_bescheid_faelligkeit


def test_bescheiddatum_faelligkeit_stimmt_mit_ao_fristen_ueberein_wochenendfall():
    # Aufgabe zur Post 03.02.2026 (Dienstag), BY: Fiktionstag 07.02.2026 (Sa,
    # nicht verschoben, Default), Monatsfrist 07.03.2026 (Sa) -> Sa->So->
    # nächster Werktag 09.03.2026 (Mo) — identisch zum ao-fristenrechner-Beispiel.
    datum, mehrdeutig = extrahiere_bescheiddatum("Bescheid vom 03.02.2026.")
    assert datum == "2026-02-03"
    assert mehrdeutig is False

    ergebnis_triage = berechne_bescheid_faelligkeit(datum, "BY")
    ergebnis_direkt = berechne_einspruchsfrist(
        bundesland="BY", aufgabe_zur_post_datum=datetime.date(2026, 2, 3))

    assert ergebnis_triage.fristende == ergebnis_direkt.fristende
    assert ergebnis_triage.fristende.isoformat() == "2026-03-09"


def test_bescheiddatum_label_datum_ohne_bescheid_vom():
    datum, mehrdeutig = extrahiere_bescheiddatum("Datum: 15.01.2026, weitere Angaben folgen.")
    assert datum == "2026-01-15"
    assert mehrdeutig is False
