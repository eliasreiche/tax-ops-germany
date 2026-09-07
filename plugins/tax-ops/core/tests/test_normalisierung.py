"""Tests für core/calc/matching/normalisierung.py.

Deckt ab: Rechtsform-Stripping (alle in CONVENTIONS/Auftrag genannten
Formen, inkl. Mehrwort-Formen und "und"-Variante), Titel-Stripping,
Umlaut-/ß-Transliteration, Interpunktion/Whitespace, sowie die separate
Token-Sortierfunktion für den Wortreihenfolge-Vergleich.
"""
from __future__ import annotations


from matching.normalisierung import normalisiere, tokenisiere  # noqa: E402


# --------------------------------------------------------------------------
# Rechtsform-Stripping
# --------------------------------------------------------------------------

import pytest


@pytest.mark.parametrize("rechtsform", [
    "GmbH", "mbH", "AG", "KG", "OHG", "GbR", "e.V.", "e.K.",
    "PartG", "PartG mbB", "SE", "Stiftung",
])
def test_rechtsform_wird_gestrippt(rechtsform):
    assert normalisiere(f"Muster {rechtsform}") == "muster"


def test_rechtsform_gmbh_co_kg_kombination():
    assert normalisiere("Muster GmbH & Co. KG") == "muster"
    assert normalisiere("Muster GmbH und Co KG") == "muster"


def test_rechtsform_ug_haftungsbeschraenkt_mit_klammer():
    # Regressionsfall: '(' ')' sind Nicht-Wortzeichen — eine \b-Assertion
    # direkt nach ')' würde am Stringende nie greifen (kein \w/\W-Übergang)
    # und die ganze Rechtsform bliebe unvollständig gestrippt.
    assert normalisiere("Muster UG (haftungsbeschränkt)") == "muster"


def test_rechtsform_stripping_ist_case_insensitiv_durch_kleinschreibung():
    assert normalisiere("Muster GMBH") == "muster"
    assert normalisiere("Muster gmbh") == "muster"


def test_rechtsform_allein_ist_kein_namensmatch():
    # Nach Stripping bleiben "mueller" und "schulze" — eindeutig
    # verschieden. Rechtsform-Gleichheit darf nie zu einem Treffer führen
    # (das übernimmt der Matching-Executor, hier nur die Normalisierungs-
    # Grundlage dafür).
    assert normalisiere("Müller GmbH") != normalisiere("Schulze GmbH")
    assert normalisiere("Müller GmbH") == "mueller"
    assert normalisiere("Schulze GmbH") == "schulze"


# --------------------------------------------------------------------------
# Titel-Stripping
# --------------------------------------------------------------------------

@pytest.mark.parametrize("eingabe,erwartet", [
    ("Dr. Max Mustermann", "max mustermann"),
    ("Prof. Dr. Erika Musterfrau", "erika musterfrau"),
    ("Dipl.-Ing. Hans Beispiel", "hans beispiel"),
    ("Dipl.-Kfm. Peter Muster", "peter muster"),
    ("LL.M. Julia Muster", "julia muster"),
    ("Dr. Dr. h.c. Max Mustermann", "max mustermann"),
])
def test_titel_wird_gestrippt(eingabe, erwartet):
    assert normalisiere(eingabe) == erwartet


def test_titel_mehrfach_whitespace_wird_kollabiert():
    assert normalisiere("Dr.  Max   Mustermann") == "max mustermann"


# --------------------------------------------------------------------------
# Umlaut-/ß-Transliteration
# --------------------------------------------------------------------------

def test_umlaut_transliteration():
    assert normalisiere("Müller-Schütz GmbH.") == "mueller schuetz"
    assert normalisiere("Straße") == "strasse"
    assert normalisiere("Größe") == "groesse"
    assert normalisiere("ÄÖÜ") == "aeoeue"


# --------------------------------------------------------------------------
# Interpunktion / Whitespace / Leereingabe
# --------------------------------------------------------------------------

def test_interpunktion_wird_zu_leerzeichen():
    assert normalisiere("Groß & Groß GbR") == "gross gross"


def test_leere_eingabe():
    assert normalisiere("") == ""
    assert tokenisiere("") == []


# --------------------------------------------------------------------------
# Tokenisierung
# --------------------------------------------------------------------------

def test_tokenisiere_zerlegt_normalisierten_text():
    assert tokenisiere("  Auto   Müller GmbH ") == ["auto", "mueller"]
