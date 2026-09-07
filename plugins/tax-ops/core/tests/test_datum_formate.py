"""Tests für core/calc/datum.py — Regressionstests zum Befund „ausgeschriebene
deutsche Daten und RFC-2822-Header werden nicht erkannt" (Abnahme
aktenkopf-extraktor/posteingang-ocr-verteilung, D12-bestätigt).

Deckt ab: ausgeschriebener deutscher Monatsname (ein-/zweistelliger Tag,
Groß-/Kleinschreibung), unzweideutige Monats-Abkürzung, RFC-2822-Header aus
E-Mail-Quelltext, sowie die Anti-Halluzinations-Grenze — ungültige/unbekannte
Eingaben bleiben `None`, es wird nichts geraten. `datum` liegt unter
`core/calc/` und wird über `plugins/conftest.py` auf `sys.path` gehängt (wie
bei `core/calc/feiertage`, siehe `fristenrechner/tests/test_feiertage_rechner.py`).
"""
from __future__ import annotations

import datum  # noqa: E402


# --------------------------------------------------------------------------
# Ausgeschriebene deutsche Monatsnamen
# --------------------------------------------------------------------------

def test_monatsname_zweistelliger_tag():
    assert datum.kanon_wert("09. Januar 2026") == "2026-01-09"


def test_monatsname_einstelliger_tag():
    assert datum.kanon_wert("9. Januar 2026") == "2026-01-09"


def test_monatsname_kleinschreibung():
    assert datum.kanon_wert("3. märz 2026") == "2026-03-03"


def test_monatsname_grossschreibung_ohne_punkt():
    assert datum.kanon_wert("15 August 2026") == "2026-08-15"


def test_monatsname_abkuerzung_unzweideutig():
    assert datum.kanon_wert("3. Apr. 2026") == "2026-04-03"


def test_monatsname_in_zeile_mehrfach():
    zeile = ("Mitteilung vom 09. Januar 2026, siehe auch Schreiben vom "
             "9. Januar 2026.")
    assert datum.kanons_in_zeile(zeile) == {"2026-01-09"}


def test_monatsname_in_zeile_ohne_falschtreffer():
    # "Mär" darf nicht als Präfix von "Märchen" greifen (Wortgrenze).
    assert datum.kanons_in_zeile("Das Märchen von 2026 war lang.") == set()


def test_monatsname_ungueltiger_kalendertag():
    assert datum.kanon_wert("31. Februar 2026") is None


# --------------------------------------------------------------------------
# RFC 2822 (E-Mail-`Date:`-Header)
# --------------------------------------------------------------------------

def test_rfc2822_vollstaendiger_header():
    assert datum.kanon_wert("Thu, 3 Apr 2026 14:22:05 +0200") == "2026-04-03"


def test_rfc2822_ohne_wochentag():
    assert datum.kanon_wert("3 Apr 2026 14:22:05 +0200") == "2026-04-03"


def test_rfc2822_zeitzone_wird_ignoriert_nicht_umgerechnet():
    # Datum wie geschrieben — kein UTC-Shift über Mitternacht, obwohl die
    # Zeitzone +0200 das Datum in UTC auf den Vortag verschieben würde.
    assert datum.kanon_wert("Thu, 3 Apr 2026 00:30:00 +0200") == "2026-04-03"


def test_rfc2822_in_email_rohtext():
    zeile = "Date: Thu, 3 Apr 2026 14:22:05 +0200 (CEST)"
    assert datum.kanons_in_zeile(zeile) == {"2026-04-03"}


def test_rfc2822_ohne_uhrzeit_nicht_erkannt():
    # Dokumentierte Grenze: kein vollständiger RFC-2822-String ohne Uhrzeit.
    # "Jun" statt "Apr", damit die deutsche Monatsabkürzung (bewusst nicht
    # belegt, siehe Modul-Docstring) den Fall nicht zufällig mitträgt.
    assert datum.kanon_wert("3 Jun 2026") is None


# --------------------------------------------------------------------------
# Anti-Halluzination — unerkannt bleibt unerkannt
# --------------------------------------------------------------------------

def test_ungueltiger_monatsname():
    assert datum.kanon_wert("9. Foobar 2026") is None
    assert datum.kanons_in_zeile("Schreiben vom 9. Foobar 2026.") == set()


def test_nonsens_string():
    assert datum.kanon_wert("kein Datum hier") is None
    assert datum.kanons_in_zeile("kein Datum hier") == set()


def test_bestehende_formate_unveraendert():
    # Ziffernformate (ISO/DE) bleiben exakt wie vor dem Fix erkannt.
    assert datum.kanon_wert("2026-01-09") == "2026-01-09"
    assert datum.kanon_wert("09.01.2026") == "2026-01-09"
    assert datum.kanon_wert("31.02.2026") is None
