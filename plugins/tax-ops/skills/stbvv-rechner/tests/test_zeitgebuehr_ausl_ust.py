"""Tests für Zeitgebühr (§ 13 StBVV), Auslagenpauschale (§ 16 StBVV) und
Umsatzsteuer (§ 15 StBVV) in core/calc/stbvv/rechner.py.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from stbvv.rechner import (
    D,
    StBVVEingabeFehler,
    berechne_auslagenpauschale,
    berechne_betragsrahmen,
    berechne_ust,
    berechne_zeitgebuehr,
)


# --------------------------------------------------------------------------
# Zeitgebühr: angefangene Viertelstunden
# --------------------------------------------------------------------------

def test_14_minuten_ist_eine_einheit():
    e = berechne_zeitgebuehr("2025-07-01", 14, referenzpunkt="untergrenze")
    assert e.details["einheiten"] == 1


def test_15_minuten_ist_eine_einheit():
    e = berechne_zeitgebuehr("2025-07-01", 15, referenzpunkt="untergrenze")
    assert e.details["einheiten"] == 1


def test_16_minuten_ist_zwei_einheiten():
    e = berechne_zeitgebuehr("2025-07-01", 16, referenzpunkt="untergrenze")
    assert e.details["einheiten"] == 2


def test_100_minuten_obergrenze():
    e = berechne_zeitgebuehr("2025-09-01", 100, referenzpunkt="obergrenze")
    assert e.details["einheiten"] == 7
    assert e.betrag == Decimal("287.00")   # 7 x 41,00


def test_stichtag_genau_am_stichtag_geht():
    e = berechne_zeitgebuehr("2025-07-01", 15, referenzpunkt="untergrenze")
    assert e.betrag == Decimal("16.50")


def test_stichtag_einen_tag_davor_wird_abgelehnt():
    with pytest.raises(StBVVEingabeFehler):
        berechne_zeitgebuehr("2025-06-30", 15, referenzpunkt="untergrenze")


def test_zeitgebuehr_rahmen_grenzen():
    with pytest.raises(StBVVEingabeFehler):
        berechne_zeitgebuehr("2025-07-01", 15, satz="16.00")   # unter 16,50
    with pytest.raises(StBVVEingabeFehler):
        berechne_zeitgebuehr("2025-07-01", 15, satz="41.01")   # über 41,00


# --------------------------------------------------------------------------
# § 34 StBVV Betragsrahmen je Einheit
# --------------------------------------------------------------------------

def test_lohnabrechnung_mittelgebuehr_fuenf_arbeitnehmer():
    e = berechne_betragsrahmen("34-2-lohnabrechnung", 5, referenzpunkt="mittelgebuehr")
    assert e.details["satz_je_einheit"] == "18.00"   # (6+30)/2
    assert e.betrag == Decimal("90.00")


def test_betragsrahmen_einheiten_muss_positive_ganzzahl_sein():
    with pytest.raises(StBVVEingabeFehler):
        berechne_betragsrahmen("34-2-lohnabrechnung", 0, referenzpunkt="mittelgebuehr")
    with pytest.raises(StBVVEingabeFehler):
        berechne_betragsrahmen("34-2-lohnabrechnung", "5", referenzpunkt="mittelgebuehr")


# --------------------------------------------------------------------------
# Auslagenpauschale (§ 16 StBVV): 20 %, höchstens 20 Euro
# --------------------------------------------------------------------------

def test_auslagenpauschale_unter_hoechstbetrag():
    betrag, _ = berechne_auslagenpauschale(D("50.00"))
    assert betrag == Decimal("10.00")   # 20 % von 50


def test_auslagenpauschale_hoechstbetrag_greift():
    betrag, _ = berechne_auslagenpauschale(D("1000.00"))
    assert betrag == Decimal("20.00")   # 20 % von 1000 wären 200, gedeckelt auf 20


def test_auslagenpauschale_genau_an_der_kappungsgrenze():
    # 20 % von 100 = 20,00 -- exakt am Höchstbetrag, keine Kappung sichtbar nötig
    betrag, _ = berechne_auslagenpauschale(D("100.00"))
    assert betrag == Decimal("20.00")


# --------------------------------------------------------------------------
# Umsatzsteuer (§ 15 StBVV)
# --------------------------------------------------------------------------

def test_ust_neunzehn_prozent():
    ust, _ = berechne_ust(D("100.00"), D("0.19"))
    assert ust == Decimal("19.00")


def test_ust_null_bei_kleinunternehmer_satz():
    ust, _ = berechne_ust(D("100.00"), D("0.00"))
    assert ust == Decimal("0.00")
