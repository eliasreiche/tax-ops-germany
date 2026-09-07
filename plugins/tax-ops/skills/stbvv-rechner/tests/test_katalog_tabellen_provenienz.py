"""Provenienz-Gate für die StBVV-Datendateien (CONVENTIONS.md P3/Anti-
Halluzination): jede Katalogzeile und jede Tabelle trägt eine `quelle_url`
auf gesetze-im-internet.de — kein Wert ohne nachvollziehbare Primärquelle.
"""
from __future__ import annotations

from stbvv.rechner import lade_katalog, lade_tabellen, D

_ERLAUBTE_HOST = "https://www.gesetze-im-internet.de/"


def test_jede_katalogzeile_hat_quelle_url():
    katalog = lade_katalog()
    assert katalog, "Katalog darf nicht leer sein"
    for id_, eintrag in katalog.items():
        assert "quelle_url" in eintrag, f"{id_}: quelle_url fehlt"
        assert eintrag["quelle_url"].startswith(_ERLAUBTE_HOST), (
            f"{id_}: quelle_url zeigt nicht auf gesetze-im-internet.de: "
            f"{eintrag['quelle_url']!r}")


def test_jede_tabelle_hat_quelle_url_und_stand_und_abrufdatum():
    tabellen = lade_tabellen()
    assert tabellen, "Tabellen dürfen nicht leer sein"
    for id_, tab in tabellen.items():
        assert tab["quelle_url"].startswith(_ERLAUBTE_HOST), id_
        assert tab["stand"], f"{id_}: stand fehlt"
        assert tab["abgerufen_am"] == "2026-09-08", id_
        assert tab["stufen"], f"{id_}: keine Wertstufen"


def test_wertgebuehr_katalogzeilen_referenzieren_bekannte_tabelle():
    katalog = lade_katalog()
    tabellen = lade_tabellen()
    for id_, eintrag in katalog.items():
        if eintrag["art"] != "wertgebuehr":
            continue
        assert eintrag["tabelle"] in tabellen, (
            f"{id_}: Tabelle '{eintrag['tabelle']}' nicht in tabellen.json")


def test_wertgebuehr_satzrahmen_konsistent_min_kleiner_max():
    katalog = lade_katalog()
    for id_, eintrag in katalog.items():
        if eintrag["art"] == "wertgebuehr":
            assert D(eintrag["satz_min"]) < D(eintrag["satz_max"]), id_
        elif eintrag["art"] == "betragsrahmen_je_einheit":
            assert D(eintrag["rahmen_min"]) < D(eintrag["rahmen_max"]), id_


def test_tabellen_stufen_streng_aufsteigend():
    tabellen = lade_tabellen()
    for id_, tab in tabellen.items():
        werte = [D(s["bis"]) for s in tab["stufen"]]
        assert werte == sorted(set(werte)), f"{id_}: Stufen nicht streng aufsteigend"
