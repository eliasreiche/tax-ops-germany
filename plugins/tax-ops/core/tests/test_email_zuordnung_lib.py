"""Unit-Tests für core/calc/zuordnung/ (P3/P4) — die wiederverwendbare
Zuordnungs-Bibliothek, unabhängig vom Executor/CLI dieses Skills.

Deckt ab: Az-Normalisierung und Z0-Suche (`az.py`), Parteiname-in-Text-Suche
Z1-Z4 inkl. eines echten False-Positive-Grenzfalls (`parteisuche.py`), sowie
die Kombination beider zu `finde_kandidaten()` inkl. `kein_treffer`-Lücke
(`zuordnung.py`).
"""
from __future__ import annotations


from zuordnung import Dokument, Kandidat, Mandat, finde_kandidaten  # noqa: E402
from zuordnung.az import az_gefunden_in_text, normalisiere_az  # noqa: E402
from zuordnung.parteisuche import suche_name_in_text  # noqa: E402


# --------------------------------------------------------------------------
# az.py — Normalisierung + Z0-Suche
# --------------------------------------------------------------------------

def test_normalisiere_az_kollabiert_whitespace():
    assert normalisiere_az("  12   O  345 / 26  ") == "12 O 345 / 26"


def test_normalisiere_az_leer():
    assert normalisiere_az("") == ""
    assert normalisiere_az(None) == ""  # type: ignore[arg-type]


def test_az_gefunden_in_text_direkter_treffer():
    assert az_gefunden_in_text("2026-001", "Unser Aktenzeichen: 2026-001, bitte...")


def test_az_gefunden_in_text_whitespace_normalisiert():
    # Az im Text mit doppeltem Leerzeichen, Az selbst einfach — beide werden
    # vor dem Vergleich normalisiert.
    assert az_gefunden_in_text("12 O 345/26", "Geschäftszeichen 12  O  345/26 des AG")


def test_az_gefunden_in_text_kein_treffer():
    assert not az_gefunden_in_text("2026-001", "Ganz anderer Text ohne Bezug.")


def test_az_gefunden_in_text_leeres_az_nie_treffer():
    assert not az_gefunden_in_text("", "2026-001 kommt hier vor")


# --------------------------------------------------------------------------
# parteisuche.py — Z1-Z4
# --------------------------------------------------------------------------

def test_z1_exakte_phrase():
    treffer = suche_name_in_text("Muster AG", "im Namen der Muster AG teilen wir mit")
    assert treffer is not None
    assert treffer.stufe == "Z1"
    assert treffer.kategorie == "treffer"


def test_z2_token_menge_andere_reihenfolge():
    treffer = suche_name_in_text("Mustermann Bau GmbH",
                                  "Betreff: GmbH Bau Mustermann - Rechnung")
    assert treffer is not None
    assert treffer.stufe == "Z2"
    assert treffer.kategorie == "treffer"


def test_z3_phonetik_schreibweisen_varianten():
    # "Schmitt" im Text, Partei "Schmidt" - Kölner Phonetik identisch (862).
    treffer = suche_name_in_text("Schmidt", "Sehr geehrter Herr Schmitt, ...")
    assert treffer is not None
    assert treffer.stufe == "Z3"
    assert treffer.kategorie == "moeglicher_treffer"


def test_z4_fuzzy_tippfehler():
    # "Mustermnn" (fehlendes 'a') ist phonetisch NICHT identisch mit
    # "Mustermann" (Kölner Phonetik 68276 vs. 682766 - Z3 greift also nicht),
    # aber zeichenketten-ähnlich genug für Z4.
    treffer = suche_name_in_text("Mustermann", "an Herrn Mustermnn zu richten",
                                  schwelle=0.85)
    assert treffer is not None
    assert treffer.stufe == "Z4"
    assert treffer.kategorie == "moeglicher_treffer"
    assert treffer.score >= 0.85


def test_false_positive_grenzfall_mueller_gmbh_vs_schulze_gmbh():
    """Rechtsform-Gleichheit allein ist nie ein Treffer (geerbt von
    core/calc/matching) — "Müller GmbH" darf nicht auf einen Text treffen,
    der nur "Schulze GmbH" enthält."""
    treffer = suche_name_in_text("Müller GmbH", "Schreiben der Schulze GmbH betreffend Lieferung")
    assert treffer is None


def test_suche_name_in_text_leerer_name_oder_text():
    assert suche_name_in_text("", "irgendein Text") is None
    assert suche_name_in_text("Mustermann", "") is None


# --------------------------------------------------------------------------
# zuordnung.py — Kombination Z0 + Z1-Z4 über eine Mandatsliste
# --------------------------------------------------------------------------

def _mandate() -> list[Mandat]:
    return [
        Mandat(az="2026-001", mandant="Beispiel GmbH", gegenseite="Muster AG",
               datei="mandate/2026-001.md"),
        Mandat(az="2026-002", mandant="Zweite Beispiel KG", gegenseite=None,
               datei="mandate/2026-002.md"),
    ]


def test_finde_kandidaten_az_treffer_hat_vorrang_vor_parteiname():
    dokument = Dokument(
        absender_name="Muster AG", betreff="Az. 2026-001 - Fristsetzung",
        textauszug="im Namen der Muster AG ...")
    kandidaten = finde_kandidaten(dokument, _mandate())
    assert len(kandidaten) == 1
    assert kandidaten[0].az == "2026-001"
    assert kandidaten[0].stufe == "Z0"
    assert kandidaten[0].kategorie == "treffer"


def test_finde_kandidaten_parteiname_ohne_az():
    dokument = Dokument(absender_name="Muster AG",
                         textauszug="im Namen der Muster AG fordern wir Sie auf")
    kandidaten = finde_kandidaten(dokument, _mandate())
    assert len(kandidaten) == 1
    assert kandidaten[0].az == "2026-001"
    assert kandidaten[0].stufe == "Z1"


def test_finde_kandidaten_kein_treffer_ist_leere_liste():
    dokument = Dokument(absender_name="Unbeteiligte Partei", betreff="Werbung",
                         textauszug="Kaufen Sie jetzt reduziert, Sonderangebot!")
    kandidaten = finde_kandidaten(dokument, _mandate())
    assert kandidaten == []


def test_finde_kandidaten_sortierung_treffer_vor_moeglichem_treffer():
    dokument = Dokument(
        betreff="",
        # "Beispiel" trifft Z1 auf Mandant 2026-001; "Schmitt"/"Schmidt"-artige
        # Phonetik gibt es hier nicht, daher nur ein Kandidat pro Mandat.
        textauszug="Schreiben der Beispiel GmbH, ferner Grüße von Zweite Beispiel KG")
    kandidaten = finde_kandidaten(dokument, _mandate())
    # Beide Mandate matchen (gemeinsames Wort "beispiel") - deterministisch
    # sortiert, keine Exception, keine Bevorzugung eines Mandats durch Zufall.
    assert {k.az for k in kandidaten} == {"2026-001", "2026-002"}
    assert all(k.kategorie == "treffer" for k in kandidaten)


def test_kandidat_ist_dataclass_mit_erwarteten_feldern():
    k = Kandidat(az="2026-001", stufe="Z0", kategorie="treffer", score=1.0,
                 begruendung="x", datei="mandate/2026-001.md")
    assert k.az == "2026-001"
    assert k.datei == "mandate/2026-001.md"
