"""Prioritäts-Matrix (Baustein 4): Grenzwerte der Restfrist-Dringlichkeit
(< 3 Werktage 'sofort', <= 10 'hoch', sonst 'normal'), das erzwungene
'hoch' bei mehrdeutigem Bescheiddatum, und die Standard-Fälle ohne
Fälligkeitsberechnung (kein Indikator, Indikator ohne Bescheid-Kategorie).
"""
from __future__ import annotations

import datetime as _dt

from triage import bewerte_mail, klassifiziere
from triage import rechner as r


def test_werktage_bis_grenzwert_sofort_unter_drei():
    heute = _dt.date(2026, 9, 8)   # Dienstag
    ziel = _dt.date(2026, 9, 10)   # Donnerstag = 2 Werktage
    assert r._werktage_bis(heute, ziel) == 2
    assert r._dringlichkeit_aus_restfrist(2) == "sofort"


def test_werktage_bis_grenzwert_hoch_bei_drei():
    heute = _dt.date(2026, 9, 8)
    ziel = _dt.date(2026, 9, 11)   # Freitag = 3 Werktage
    assert r._werktage_bis(heute, ziel) == 3
    assert r._dringlichkeit_aus_restfrist(3) == "hoch"


def test_werktage_bis_grenzwert_hoch_bei_zehn():
    assert r._dringlichkeit_aus_restfrist(10) == "hoch"


def test_werktage_bis_grenzwert_normal_ab_elf():
    assert r._dringlichkeit_aus_restfrist(11) == "normal"


def test_werktage_bis_negativ_bei_ueberfaelligkeit_ist_sofort():
    heute = _dt.date(2026, 9, 8)
    ziel = _dt.date(2026, 9, 1)
    werktage = r._werktage_bis(heute, ziel)
    assert werktage < 0
    assert r._dringlichkeit_aus_restfrist(werktage) == "sofort"


def test_mehrdeutiges_bescheiddatum_erzwingt_prioritaet_hoch():
    indikatoren = r.erkenne_indikatoren("Steuerbescheid", "")
    text = "Bescheid vom 01.09.2026, alternativ Datum 03.09.2026 laut Poststempel."
    klasse = klassifiziere(indikatoren, "Steuerbescheid", text)
    prioritaet, faelligkeit, unklar, kette = bewerte_mail(
        indikatoren, klasse, "Steuerbescheid", text, "NW", _dt.date(2026, 9, 8))
    assert prioritaet == "hoch"
    assert faelligkeit is None
    assert unklar is True
    assert any(s.ergebnis == "[unklar]" for s in kette)


def test_kein_indikator_ohne_newsletter_ist_normal():
    prioritaet, faelligkeit, unklar, _ = bewerte_mail(
        [], "unklar", "Allgemeine Anfrage", "Text ohne Indikator",
        "NW", _dt.date(2026, 9, 8))
    assert prioritaet == "normal"
    assert faelligkeit is None
    assert unklar is False


def test_kein_indikator_aber_klasse_info_ist_prioritaet_info():
    prioritaet, faelligkeit, unklar, _ = bewerte_mail(
        [], "info", "Rundschreiben", "Nur zur Kenntnisnahme.",
        "NW", _dt.date(2026, 9, 8))
    assert prioritaet == "info"


def test_indikator_ohne_bescheid_kategorie_uebernimmt_standard_dringlichkeit():
    indikatoren = r.erkenne_indikatoren("", "Dies ist eine Mahnung.")
    prioritaet, faelligkeit, unklar, _ = bewerte_mail(
        indikatoren, "aufgabe", "Mahnung", "Dies ist eine Mahnung.",
        "NW", _dt.date(2026, 9, 8))
    assert prioritaet == "sofort"   # Mahnung/Vollstreckung: Standard-Dringlichkeit "sofort"
    assert faelligkeit is None
    assert unklar is False
