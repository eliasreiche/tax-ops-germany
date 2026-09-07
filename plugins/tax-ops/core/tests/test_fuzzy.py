"""Tests für core/calc/matching/fuzzy.py — Ähnlichkeitsmaße."""
from __future__ import annotations


import pytest


from matching.fuzzy import sequenz_ratio, token_alignment_ratio  # noqa: E402


# --------------------------------------------------------------------------
# sequenz_ratio
# --------------------------------------------------------------------------

def test_sequenz_ratio_identische_strings_ist_1():
    assert sequenz_ratio("mustermann", "mustermann") == 1.0


def test_sequenz_ratio_leere_strings_ist_1():
    assert sequenz_ratio("", "") == 1.0


def test_sequenz_ratio_komplett_verschieden_ist_niedrig():
    assert sequenz_ratio("mueller", "schulze") < 0.5


def test_sequenz_ratio_tippfehler_ist_hoch():
    assert sequenz_ratio("mustermann", "mustremann") > 0.85


def test_sequenz_ratio_symmetrisch():
    assert sequenz_ratio("abc", "abd") == sequenz_ratio("abd", "abc")


# --------------------------------------------------------------------------
# token_alignment_ratio
# --------------------------------------------------------------------------

def test_token_alignment_identische_listen_ist_1():
    assert token_alignment_ratio(["auto", "mueller"], ["auto", "mueller"]) == 1.0


def test_token_alignment_ist_wortreihenfolge_unabhaengig():
    assert token_alignment_ratio(["auto", "mueller"], ["mueller", "auto"]) == 1.0


def test_token_alignment_leere_liste_ist_0():
    assert token_alignment_ratio([], ["auto"]) == 0.0
    assert token_alignment_ratio(["auto"], []) == 0.0
    assert token_alignment_ratio([], []) == 0.0


def test_token_alignment_teilweise_ueberschneidung():
    # "mueller" matcht sich selbst perfekt (1.0); das verbleibende Paar
    # ("handel" / "voellig-anders", da bei gleicher Tokenanzahl kein Token
    # unzugeordnet bleibt) trägt nur seinen eigenen, niedrigeren
    # sequenz_ratio-Wert bei -> Gesamtscore liegt spürbar unter 1.0, aber
    # über dem reinen Zufallsniveau.
    score = token_alignment_ratio(["mueller", "handel"], ["mueller", "voellig-anders"])
    assert 0.6 < score < 0.8


def test_token_alignment_jedes_token_hoechstens_einmal_verbraucht():
    # Zwei identische Tokens auf einer Seite dürfen nicht beide gegen
    # dasselbe einzelne Token der anderen Seite matchen.
    score = token_alignment_ratio(["mueller", "mueller"], ["mueller"])
    assert score == pytest.approx(0.5)
