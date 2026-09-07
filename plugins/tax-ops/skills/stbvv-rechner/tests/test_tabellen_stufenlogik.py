"""Tests für die Wertstufen-Suche und Fortschreibung (core/calc/stbvv/rechner.py).

Golden-Fälle je Tabelle: erste, eine mittlere, letzte Wertstufe; Wert genau
auf der Stufengrenze und ein Cent darüber; Fortschreibung oberhalb der
letzten Stufe; Zehntelrahmen-Grenzen (Untergrenze/Obergrenze zulässig,
außerhalb abgelehnt); Mindestgegenstandswert-Anhebung.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from stbvv.rechner import (
    D,
    StBVVEingabeFehler,
    berechne_wertgebuehr,
    lade_katalog,
    lade_tabellen,
    volle_gebuehr,
)

TAB = lade_tabellen()
KAT = lade_katalog()


# --------------------------------------------------------------------------
# Tabelle A (Anlage 1) — erste/mittlere/letzte Stufe, Grenze +/- 1 Cent
# --------------------------------------------------------------------------

def test_tabelle_a_erste_stufe():
    r = volle_gebuehr("A", D("300"), TAB)
    assert r.volle_gebuehr == D("31")


def test_tabelle_a_mittlere_stufe():
    r = volle_gebuehr("A", D("50000"), TAB)
    assert r.volle_gebuehr == D("1304")


def test_tabelle_a_letzte_stufe():
    r = volle_gebuehr("A", D("600000"), TAB)
    assert r.volle_gebuehr == D("3404")


def test_tabelle_a_stufengrenze_exakt_vs_ein_cent_darueber():
    genau = volle_gebuehr("A", D("2500"), TAB)
    darueber = volle_gebuehr("A", D("2500.01"), TAB)
    assert genau.volle_gebuehr == D("200")
    assert darueber.volle_gebuehr == D("235")   # nächste Stufe (3000 -> 235)


def test_tabelle_a_fortschreibung_ueber_letzte_stufe():
    # 600 000,01 -> erste angefangene 50 000-Einheit der ersten Fortschreibungsstufe (149)
    r = volle_gebuehr("A", D("600000.01"), TAB)
    assert r.volle_gebuehr == D("3553.00")   # 3404 + 149
    # exakt eine Stufe weiter (650 000 = 600 000 + 50 000)
    r2 = volle_gebuehr("A", D("650000"), TAB)
    assert r2.volle_gebuehr == D("3553.00")
    r3 = volle_gebuehr("A", D("650000.01"), TAB)
    assert r3.volle_gebuehr == D("3702.00")  # 3404 + 2*149


def test_tabelle_a_fortschreibung_zweite_stufe_ab_5_millionen():
    # bei 5 000 000 endet die erste Fortschreibungsstufe (149/50000),
    # ab da gilt 112/50000
    r_grenze = volle_gebuehr("A", D("5000000"), TAB)
    r_danach = volle_gebuehr("A", D("5000000.01"), TAB)
    assert r_danach.volle_gebuehr == r_grenze.volle_gebuehr + D("112")


# --------------------------------------------------------------------------
# Tabelle B (Anlage 2) und C (Anlage 3) — je erste/mittlere/letzte Stufe
# --------------------------------------------------------------------------

def test_tabelle_b_erste_mittlere_letzte_stufe():
    assert volle_gebuehr("B", D("3000"), TAB).volle_gebuehr == D("49")
    assert volle_gebuehr("B", D("100000"), TAB).volle_gebuehr == D("369")
    assert volle_gebuehr("B", D("50000000"), TAB).volle_gebuehr == D("6923")


def test_tabelle_b_fortschreibung():
    r = volle_gebuehr("B", D("50000000.01"), TAB)
    assert r.volle_gebuehr == D("6923") + D("273")


def test_tabelle_c_erste_mittlere_letzte_stufe():
    assert volle_gebuehr("C", D("15000"), TAB).volle_gebuehr == D("72")
    assert volle_gebuehr("C", D("100000"), TAB).volle_gebuehr == D("188")
    assert volle_gebuehr("C", D("500000"), TAB).volle_gebuehr == D("512")


def test_tabelle_c_fortschreibung():
    r = volle_gebuehr("C", D("500000.01"), TAB)
    assert r.volle_gebuehr == D("512") + D("36")


# --------------------------------------------------------------------------
# Tabelle D Teil a: kein Fortschreibungsschema implementiert -> Exit-Ursache
# --------------------------------------------------------------------------

def test_tabelle_d_teil_a_oberhalb_letzter_stufe_lehnt_ab():
    with pytest.raises(StBVVEingabeFehler):
        volle_gebuehr("D_teil_a", D("1000.01"), TAB)


def test_tabelle_d_teil_a_letzte_stufe_geht_noch():
    assert volle_gebuehr("D_teil_a", D("1000"), TAB).volle_gebuehr == D("1843")


# --------------------------------------------------------------------------
# Zehntelrahmen-Grenzen (§ 11 StBVV): Unter-/Obergrenze zulässig, außerhalb nicht
# --------------------------------------------------------------------------

def test_zehntelrahmen_untergrenze_und_obergrenze_zulaessig():
    unten = berechne_wertgebuehr("24-1-nr1-est-erklaerung", "50000", referenzpunkt="untergrenze")
    oben = berechne_wertgebuehr("24-1-nr1-est-erklaerung", "50000", referenzpunkt="obergrenze")
    assert unten.details["satz"] == "0.1"
    assert oben.details["satz"] == "0.6"


def test_zehntelrahmen_mittelgebuehr():
    mitte = berechne_wertgebuehr("24-1-nr1-est-erklaerung", "50000", referenzpunkt="mittelgebuehr")
    assert mitte.details["satz"] == "0.35"   # (0.1 + 0.6) / 2


def test_satz_ausserhalb_rahmen_wird_abgelehnt():
    with pytest.raises(StBVVEingabeFehler):
        berechne_wertgebuehr("24-1-nr1-est-erklaerung", "50000", satz="0.9")
    with pytest.raises(StBVVEingabeFehler):
        berechne_wertgebuehr("24-1-nr1-est-erklaerung", "50000", satz="0.05")


def test_satz_und_referenzpunkt_gleichzeitig_ist_fehler():
    with pytest.raises(StBVVEingabeFehler):
        berechne_wertgebuehr("24-1-nr1-est-erklaerung", "50000", satz="0.3", referenzpunkt="obergrenze")


def test_weder_satz_noch_referenzpunkt_ist_fehler():
    with pytest.raises(StBVVEingabeFehler):
        berechne_wertgebuehr("24-1-nr1-est-erklaerung", "50000")


# --------------------------------------------------------------------------
# Mindestgegenstandswert (§ 24 Abs. 1 Nr. 1 StBVV: mindestens 8 000 Euro)
# --------------------------------------------------------------------------

def test_mindestwert_wird_angehoben():
    ergebnis = berechne_wertgebuehr("24-1-nr1-est-erklaerung", "1000", referenzpunkt="mittelgebuehr")
    assert ergebnis.details["mindestwert_gegriffen"] is True
    assert ergebnis.details["gegenstandswert_angewendet"] == "8000"


def test_mindestwert_nicht_angehoben_wenn_darueber():
    ergebnis = berechne_wertgebuehr("24-1-nr1-est-erklaerung", "50000", referenzpunkt="mittelgebuehr")
    assert ergebnis.details["mindestwert_gegriffen"] is False


# --------------------------------------------------------------------------
# Erstberatungs-Kappung (§ 21 Abs. 1 Satz 2 StBVV)
# --------------------------------------------------------------------------

def test_erstberatung_verbraucher_kappung_greift():
    ergebnis = berechne_wertgebuehr(
        "21-1-rat-auskunft", "50000", referenzpunkt="obergrenze",
        erstberatung_verbraucher=True)
    assert ergebnis.betrag == Decimal("190.00")


def test_erstberatung_verbraucher_nur_fuer_21_1_zulaessig():
    with pytest.raises(StBVVEingabeFehler):
        berechne_wertgebuehr(
            "24-1-nr1-est-erklaerung", "50000", referenzpunkt="mittelgebuehr",
            erstberatung_verbraucher=True)


def test_unbekannte_tatbestand_id():
    with pytest.raises(StBVVEingabeFehler):
        berechne_wertgebuehr("nicht-vorhanden", "1000", referenzpunkt="mittelgebuehr")
