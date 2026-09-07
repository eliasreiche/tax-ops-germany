"""Mandanten-Zuordnung (Baustein 1): Domain/Mandantennummer (literal) und
core/calc/matching Stufen S1-S4 (Name/Alias gegen Absender-Name/Betreff),
sowie die Enthaltung bei fehlendem oder mehrdeutigem Treffer.
"""
from __future__ import annotations

from triage import Mandant, zuordne_mandant


def test_domain_treffer():
    m = [Mandant(name="Backstube Sonnenschein GmbH", aliasse=["backstube.example"])]
    treffer = zuordne_mandant("Petra Beispiel", "p.beispiel@backstube.example",
                              "Frage", "", m)
    assert treffer is not None
    mandant, t = treffer
    assert mandant.name == "Backstube Sonnenschein GmbH"
    assert t.stufe == "domain"
    assert t.kategorie == "treffer"


def test_mandantennummer_treffer_in_text():
    m = [Mandant(name="Muster-Handel KG", mandantennummer="23/456/78901")]
    treffer = zuordne_mandant("Unbekannt", "irgendwer@sonstwo.example",
                              "Ihre Steuernummer 23/456/78901", "", m)
    assert treffer is not None
    mandant, t = treffer
    assert mandant.name == "Muster-Handel KG"
    assert t.stufe == "mandantennummer"
    assert t.kategorie == "treffer"


def test_s1_exakter_namenstreffer():
    m = [Mandant(name="Peter Mueller")]
    treffer = zuordne_mandant("Peter Mueller", "x@nirgends.example", "Betreff", "", m)
    assert treffer is not None
    _, t = treffer
    assert t.stufe == "S1"
    assert t.kategorie == "treffer"


def test_s2_token_teilmenge_ueber_betreff():
    m = [Mandant(name="Muster-Handel KG")]
    treffer = zuordne_mandant("Vollstreckungsstelle", "vollstreckung@fa.example",
                              "Mahnung Muster-Handel KG", "", m)
    assert treffer is not None
    _, t = treffer
    assert t.stufe == "S2"
    assert t.kategorie == "treffer"


def test_s3_phonetischer_treffer():
    m = [Mandant(name="Meyer GmbH")]
    treffer = zuordne_mandant("Maier GmbH", "x@nirgends.example",
                              "Betreff ohne Namensbezug", "", m)
    assert treffer is not None
    _, t = treffer
    assert t.stufe == "S3"
    assert t.kategorie == "moeglicher_treffer"


def test_s4_fuzzy_treffer():
    m = [Mandant(name="Musterfirma GmbH")]
    treffer = zuordne_mandant("Mustefirma GmbH", "x@nirgends.example",
                              "Betreff ohne Namensbezug", "", m)
    assert treffer is not None
    _, t = treffer
    assert t.stufe == "S4"
    assert t.kategorie == "moeglicher_treffer"


def test_unzugeordnet_ohne_jeden_treffer():
    m = [Mandant(name="Ganz Andere Firma")]
    treffer = zuordne_mandant("Voellig Unbekannt", "x@nirgends.example",
                              "Betreff ohne jeden Bezug", "", m)
    assert treffer is None


def test_unzugeordnet_bei_gleichstand():
    # Zwei Mandanten treffen auf derselben besten Stufe mit demselben Score
    # zu -> Enthaltung statt Raten (wie Z2N in core/calc/zuordnung).
    m = [Mandant(name="Firma A"), Mandant(name="Firma B")]
    treffer = zuordne_mandant("Firma A und Firma B", "x@nirgends.example", "", "", m)
    assert treffer is None


# --------------------------------------------------------------------------
# Gemeinsamer Namensbestandteil ("Müller GmbH" vs. "Müller & Sohn KG"): ein
# bloßer Nachname/Firmenkern darf nicht allein wegen der spezifischeren Stufe
# (S1 vs. S2) auf die kürzere Firma zuschlagen — siehe Docstring von
# `zuordne_mandant`.
# --------------------------------------------------------------------------

_MUELLER_MANDANTEN = [Mandant(name="Müller GmbH"), Mandant(name="Müller & Sohn KG")]


def test_gemeinsamer_namensbestandteil_text_nennt_kg():
    treffer = zuordne_mandant(
        "Mueller", "inh@mueller-sohn.example", "Steuerliche Frage",
        "Guten Tag, wir von Mueller & Sohn KG haben eine Frage.", _MUELLER_MANDANTEN)
    assert treffer is not None
    mandant, t = treffer
    assert mandant.name == "Müller & Sohn KG"
    assert t.stufe == "Name im Text"
    assert t.kategorie == "treffer"


def test_gemeinsamer_namensbestandteil_ohne_textbeleg_ist_moeglicher_treffer():
    treffer = zuordne_mandant(
        "Mueller", "inh@mueller-sohn.example", "Steuerliche Frage",
        "Guten Tag, wir haben eine Frage zur Steuer.", _MUELLER_MANDANTEN)
    assert treffer is not None
    _, t = treffer
    assert t.stufe == "mehrdeutig"
    assert t.kategorie == "moeglicher_treffer"
    assert t.begruendung == "mehrdeutig: gemeinsamer Namensbestandteil"
    assert set(t.kandidaten) == {"Müller GmbH", "Müller & Sohn KG"}


def test_gemeinsamer_namensbestandteil_text_nennt_gmbh():
    treffer = zuordne_mandant(
        "Mueller", "inh@mueller-sohn.example", "Steuerliche Frage",
        "Guten Tag, wir von Müller GmbH haben eine Frage.", _MUELLER_MANDANTEN)
    assert treffer is not None
    mandant, t = treffer
    assert mandant.name == "Müller GmbH"
    assert t.stufe == "Name im Text"
    assert t.kategorie == "treffer"
