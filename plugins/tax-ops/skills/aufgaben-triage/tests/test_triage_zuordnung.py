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
