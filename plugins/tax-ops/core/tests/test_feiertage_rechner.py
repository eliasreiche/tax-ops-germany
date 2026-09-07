"""Tests für core/calc/feiertage — Feiertags-Rechner (P3/P4).

Deckt ab: Gaußsche Osterformel (Fassung Butcher/Meeus), bundeseinheitliche
und länderspezifische Feiertage, Jahres-Gating neu eingeführter Feiertage,
Buß- und Bettag (nur SN), teilgebietliche Feiertage (ehrliche Kennzeichnung,
nie stillschweigend), Eingabe-Validierung und Verlässlichkeits-Hinweise.
"""
from __future__ import annotations

import datetime as dt

import pytest


import feiertage  # noqa: E402


# --------------------------------------------------------------------------
# Osterformel
# --------------------------------------------------------------------------

@pytest.mark.parametrize("jahr, erwartet", [
    (2000, dt.date(2000, 4, 23)),
    (2008, dt.date(2008, 3, 23)),
    (2024, dt.date(2024, 3, 31)),
    (2025, dt.date(2025, 4, 20)),
    (2026, dt.date(2026, 4, 5)),
    (2038, dt.date(2038, 4, 25)),   # spätestmöglicher Ostertermin
    (1818, dt.date(1818, 3, 22)),   # frühestmöglicher Ostertermin
    # Ausnahmejahre der Gaußschen Grundformel (Befund 7b): hier greifen die
    # säkularen Korrekturen — eine unkorrigierte Formel läge daneben.
    (1954, dt.date(1954, 4, 18)),
    (1981, dt.date(1981, 4, 19)),
    (2049, dt.date(2049, 4, 18)),
    (2076, dt.date(2076, 4, 19)),
])
def test_ostersonntag(jahr, erwartet):
    assert feiertage.ostersonntag(jahr) == erwartet


def test_ostersonntag_ausserhalb_gueltigkeit():
    with pytest.raises(ValueError):
        feiertage.ostersonntag(1582)
    with pytest.raises(ValueError):
        feiertage.ostersonntag(4100)


# --------------------------------------------------------------------------
# Bundeseinheitliche Feiertage
# --------------------------------------------------------------------------

def _daten(jahr, land, **kw):
    return {f.datum for f in feiertage.feiertage(jahr, land, **kw)}


def test_bundeseinheitliche_in_allen_laendern():
    erwartet_2026 = {
        dt.date(2026, 1, 1),    # Neujahr
        dt.date(2026, 4, 3),    # Karfreitag
        dt.date(2026, 4, 6),    # Ostermontag
        dt.date(2026, 5, 1),    # Tag der Arbeit
        dt.date(2026, 5, 14),   # Christi Himmelfahrt
        dt.date(2026, 5, 25),   # Pfingstmontag
        dt.date(2026, 10, 3),   # Tag der Deutschen Einheit
        dt.date(2026, 12, 25),  # 1. Weihnachtstag
        dt.date(2026, 12, 26),  # 2. Weihnachtstag
    }
    for land in feiertage.BUNDESLAENDER:
        assert erwartet_2026 <= _daten(2026, land), land


# --------------------------------------------------------------------------
# Länderspezifische Feiertage
# --------------------------------------------------------------------------

def test_heilige_drei_koenige():
    for land in ("BW", "BY", "ST"):
        assert dt.date(2026, 1, 6) in _daten(2026, land)
    for land in ("BE", "NW", "HH"):
        assert dt.date(2026, 1, 6) not in _daten(2026, land)


def test_fronleichnam_landesweit_und_fehlend():
    fronleichnam_2026 = dt.date(2026, 6, 4)   # Ostern 05.04. + 60
    for land in ("BW", "BY", "HE", "NW", "RP", "SL"):
        eintraege = [f for f in feiertage.feiertage(2026, land)
                     if f.datum == fronleichnam_2026]
        assert eintraege and eintraege[0].geltung == feiertage.GELTUNG_LANDESWEIT, land
    assert fronleichnam_2026 not in _daten(2026, "BE")
    assert fronleichnam_2026 not in _daten(2026, "HH")


def test_buss_und_bettag_nur_sachsen():
    # Mittwoch vor dem 23.11.
    assert feiertage.buss_und_bettag(2023) == dt.date(2023, 11, 22)
    assert feiertage.buss_und_bettag(2024) == dt.date(2024, 11, 20)
    assert feiertage.buss_und_bettag(2026) == dt.date(2026, 11, 18)
    assert dt.date(2026, 11, 18) in _daten(2026, "SN")
    for land in ("BY", "BE", "TH", "BW", "NW"):
        assert dt.date(2026, 11, 18) not in _daten(2026, land), land


def test_buss_und_bettag_wenn_23_nov_mittwoch():
    # 23.11.2033 ist selbst ein Mittwoch -> Feiertag ist der Mittwoch davor.
    assert dt.date(2033, 11, 23).weekday() == 2
    assert feiertage.buss_und_bettag(2033) == dt.date(2033, 11, 16)


def test_reformationstag_jahres_gating():
    reformationstag = dt.date(2018, 10, 31)
    for land in ("BB", "MV", "SN", "ST", "TH", "HB", "HH", "NI", "SH"):
        assert reformationstag in _daten(2018, land), land
    assert reformationstag not in _daten(2018, "NW")
    # HB/HH/NI/SH erst ab 2018:
    assert dt.date(2016, 10, 31) not in _daten(2016, "HH")
    assert dt.date(2016, 10, 31) in _daten(2016, "SN")


def test_reformationstag_2017_bundesweit_einmalig():
    for land in ("NW", "BY", "BE", "HH", "BW"):
        assert dt.date(2017, 10, 31) in _daten(2017, land), land
    # und kein Doppel-Eintrag in den Stamm-Ländern:
    eintraege = [f for f in feiertage.feiertage(2017, "SN")
                 if f.datum == dt.date(2017, 10, 31)]
    assert len(eintraege) == 1


def test_frauentag_gating():
    assert dt.date(2019, 3, 8) in _daten(2019, "BE")
    assert dt.date(2018, 3, 8) not in _daten(2018, "BE")
    assert dt.date(2023, 3, 8) in _daten(2023, "MV")
    assert dt.date(2022, 3, 8) not in _daten(2022, "MV")
    assert dt.date(2023, 3, 8) not in _daten(2023, "BY")


def test_weltkindertag_gating():
    assert dt.date(2019, 9, 20) in _daten(2019, "TH")
    assert dt.date(2018, 9, 20) not in _daten(2018, "TH")
    assert dt.date(2019, 9, 20) not in _daten(2019, "BE")


def test_maria_himmelfahrt_sl_landesweit():
    eintraege = [f for f in feiertage.feiertage(2026, "SL")
                 if f.datum == dt.date(2026, 8, 15)]
    assert eintraege and eintraege[0].geltung == feiertage.GELTUNG_LANDESWEIT


def test_brandenburg_oster_und_pfingstsonntag():
    assert dt.date(2026, 4, 5) in _daten(2026, "BB")    # Ostersonntag
    assert dt.date(2026, 5, 24) in _daten(2026, "BB")   # Pfingstsonntag
    assert dt.date(2026, 4, 5) not in _daten(2026, "BE")


def test_tag_der_befreiung_berlin_einmalig():
    assert dt.date(2020, 5, 8) in _daten(2020, "BE")
    assert dt.date(2025, 5, 8) in _daten(2025, "BE")
    assert dt.date(2021, 5, 8) not in _daten(2021, "BE")
    assert dt.date(2020, 5, 8) not in _daten(2020, "BB")


def test_zusammenfallende_feiertage_bleiben_beide_erhalten():
    # 2008: Christi Himmelfahrt fällt auf den 1. Mai — beide Einträge da.
    namen = {f.name for f in feiertage.feiertage(2008, "BE")
             if f.datum == dt.date(2008, 5, 1)}
    assert "Tag der Arbeit" in namen
    assert "Christi Himmelfahrt" in namen


# --------------------------------------------------------------------------
# Teilgebietliche Feiertage — ehrliche Kennzeichnung
# --------------------------------------------------------------------------

def test_teilgebietliche_bayern():
    teil = {(f.datum, f.name): f for f in feiertage.feiertage(2026, "BY")
            if f.geltung == feiertage.GELTUNG_TEILGEBIETLICH}
    assert (dt.date(2026, 8, 15), "Mariä Himmelfahrt") in teil
    assert (dt.date(2026, 8, 8), "Augsburger Hohes Friedensfest") in teil
    for f in teil.values():
        assert f.hinweis  # nie ohne Erklärung


def test_teilgebietlich_fronleichnam_sn_th():
    fronleichnam_2026 = dt.date(2026, 6, 4)
    for land in ("SN", "TH"):
        eintraege = [f for f in feiertage.feiertage(2026, land)
                     if f.datum == fronleichnam_2026]
        assert eintraege, land
        assert eintraege[0].geltung == feiertage.GELTUNG_TEILGEBIETLICH, land


def test_teilgebietliche_abschaltbar():
    ohne = feiertage.feiertage(2026, "BY", mit_teilgebietlichen=False)
    assert all(f.geltung != feiertage.GELTUNG_TEILGEBIETLICH for f in ohne)


def test_ist_feiertag_teilgebietlich_nie_stillschweigend():
    auskunft = feiertage.ist_feiertag(dt.date(2025, 8, 15), "BY")
    assert auskunft.gesetzlich is False          # nicht landesweit!
    assert auskunft.teilgebietlich is True
    assert auskunft.teilgebiet_name == "Mariä Himmelfahrt"
    assert auskunft.warnungen                    # Warnung Pflicht
    # In SL dagegen landesweit:
    assert feiertage.ist_feiertag(dt.date(2025, 8, 15), "SL").gesetzlich is True
    # In BW gar nicht:
    bw = feiertage.ist_feiertag(dt.date(2025, 8, 15), "BW")
    assert bw.gesetzlich is False and bw.teilgebietlich is False


# --------------------------------------------------------------------------
# ist_feiertag / Validierung / Hinweise
# --------------------------------------------------------------------------

def test_ist_feiertag_einfach():
    assert feiertage.ist_feiertag(dt.date(2026, 1, 1), "NW").gesetzlich is True
    assert feiertage.ist_feiertag(dt.date(2026, 1, 2), "NW").gesetzlich is False
    assert feiertage.ist_feiertag(dt.date(2026, 1, 6), "BY").gesetzlich is True
    assert feiertage.ist_feiertag(dt.date(2026, 1, 6), "BE").gesetzlich is False


def test_unbekanntes_bundesland():
    with pytest.raises(ValueError):
        feiertage.feiertage(2026, "XX")
    with pytest.raises(ValueError):
        feiertage.ist_feiertag(dt.date(2026, 1, 1), "Bayern")


def test_kleinschreibung_wird_akzeptiert():
    assert feiertage.ist_feiertag(dt.date(2026, 1, 6), "by").gesetzlich is True


def test_liste_sortiert_und_vollstaendig():
    for land in feiertage.BUNDESLAENDER:
        liste = feiertage.feiertage(2026, land)
        daten = [f.datum for f in liste]
        assert daten == sorted(daten), land
        assert len(liste) >= 9, land   # mindestens die bundeseinheitlichen


def test_jahres_hinweise_altjahre():
    hinweise = feiertage.jahres_hinweise(1990, "NW")
    assert any("1995" in h for h in hinweise)
    assert not any("1995" in h for h in feiertage.jahres_hinweise(2026, "NW"))
