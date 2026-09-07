"""Tests für core/calc/matching/koelner_phonetik.py — Kölner Phonetik.

Deckt ab: das Lehrbuch-Referenzbeispiel des Verfahrens, die klassischen
Schreibweisen-Äquivalenzklassen (Meyer/Maier/Mayr/Meier, Schmidt/Schmitt),
sowie gezielte Einzel-Kontextregeln (C im/nicht im Anlaut, P vor/nicht vor H,
X nach/nicht nach C-K-Q) an synthetischen Wörtern, um jede Zeile der
Kodierungstabelle im Docstring von koelner_phonetik.py unabhängig
abzusichern.
"""
from __future__ import annotations


from matching.koelner_phonetik import code  # noqa: E402


# --------------------------------------------------------------------------
# Referenzfall (Lehrbuchbeispiel des Verfahrens)
# --------------------------------------------------------------------------

def test_referenzfall_mueller_luedenscheidt():
    assert code("Müller-Lüdenscheidt") == "65752682"


# --------------------------------------------------------------------------
# Klassische Äquivalenzklassen (Hauptanwendungsfall der Kölner Phonetik)
# --------------------------------------------------------------------------

def test_meyer_maier_mayr_meier_gleiche_klasse():
    codes = {code("Meyer"), code("Maier"), code("Mayr"), code("Meier")}
    assert len(codes) == 1
    assert codes == {"67"}


def test_schmidt_schmitt_gleiche_klasse():
    assert code("Schmidt") == code("Schmitt") == "862"


def test_unkodierbare_woerter_ergeben_leeren_code():
    # Wörter ohne kodierbare Buchstaben (z. B. nur Ziffern/Symbole) ergeben
    # einen leeren Code — der Vergleich (Stufe S3) verwirft ihn.
    assert code("123") == ""
    assert code("") == ""


# --------------------------------------------------------------------------
# Einzel-Kontextregeln (synthetische Wörter, siehe Docstring-Tabelle)
# --------------------------------------------------------------------------

def test_c_im_anlaut_vor_vokal_ist_4():
    # "Cäcilie" -> transliteriert "Cacilie": C im Anlaut vor A (in der
    # Anlaut-Menge AHKLOQRUX) -> 4; zweites C (nicht im Anlaut, vor I,
    # das nicht in AHKOQUX liegt) -> 8.
    assert code("Cäcilie") == "485"


def test_p_vor_h_ist_3_sonst_1():
    assert code("Kaph") == "43"   # P vor H -> 3
    assert code("Kapa") == "41"   # P nicht vor H -> 1


def test_x_nach_ckq_ist_8_sonst_48():
    assert code("Akxo") == "048"   # X nach K -> 8 (ein Zeichen)
    assert code("Alex") == "0548"  # X nach E (kein C/K/Q) -> 48 (zwei Zeichen)


def test_d_t_vor_csz_ist_8_sonst_2():
    # D vor S (in C/S/Z) -> 8, kollabiert mit dem folgenden S zu einem "8";
    # zum Vergleich: D vor O (kein C/S/Z) -> 2.
    assert code("Adso") == "08"
    assert code("Adolf") == "0253"


def test_h_traegt_keinen_code_und_wird_uebersprungen():
    # H erzeugt keinen eigenen Code, unterbricht aber auch nicht die
    # Kontextprüfung der Nachbarbuchstaben (siehe Modul-Docstring).
    assert code("Ahmed") == code("Amed")
