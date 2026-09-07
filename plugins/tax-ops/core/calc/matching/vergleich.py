"""vergleich — Namensvergleich in vier Stufen S1-S4 (P3-Bibliothek).

Vergleicht zwei Partei-/Personennamen (natürliche und juristische Personen)
und liefert die **erste** zutreffende Stufe — absteigend in Sicherheit,
aufsteigend im Rückruf:

    S1  exakt gleich nach Normalisierung                    -> treffer
    S2  gleiche Token-Menge oder Token-Teilmenge            -> treffer
    S3  Kölner Phonetik je Token identisch                  -> moeglicher_treffer
    S4  Fuzzy-Ähnlichkeit >= Schwelle                       -> moeglicher_treffer

`None` bedeutet: keine Stufe trifft zu (`kein_treffer`). Die Bibliothek
entscheidet nichts über die Rechtsfolge — sie liefert Stufe, Score und
Begründung; die Bewertung (Kollision, Sanktionstreffer) bleibt Sache des
aufrufenden Executors und am Ende der Kanzlei (Deterministik-Grenze, P3).

Genutzt von `interessenkollision-check` (Parteien gegen Mandanten-/
Gegnerliste) und `gwg-live-screening` (Parteien gegen Sanktionslisten-
Einträge inkl. Aliase) — vorher zweimal implementiert. Für den Vergleich
**Name gegen Fließtext** ist nicht diese Kaskade zuständig, sondern
`core/calc/zuordnung/parteisuche.py` (Stufen Z1-Z4, andere Kombination
derselben Bausteine).

Nur Standardbibliothek, keine Persistierung, kein Netzwerkzugriff.
"""
from __future__ import annotations

from dataclasses import dataclass

from .fuzzy import sequenz_ratio, token_alignment_ratio
from .koelner_phonetik import code as koelner_code
from .normalisierung import normalisiere, tokenisiere

STUFE_TREFFER = "treffer"
STUFE_MOEGLICH = "moeglicher_treffer"


@dataclass
class NamensTreffer:
    """Ergebnis eines Namensvergleichs (Feldnamen wie im Report der Skills)."""
    regel: str        # "S1" | "S2" | "S3" | "S4"
    stufe: str        # "treffer" | "moeglicher_treffer"
    score: float
    begruendung: str


def _s2_token_mengen(tokens_a: list[str], tokens_b: list[str]) -> NamensTreffer | None:
    menge_a, menge_b = set(tokens_a), set(tokens_b)
    if not menge_a or not menge_b:
        return None
    if menge_a == menge_b:
        return NamensTreffer("S2", STUFE_TREFFER, 1.0,
                             f"Token-Mengen-Gleichheit nach Normalisierung (Wortreihenfolge "
                             f"unerheblich): {{{', '.join(sorted(menge_a))}}}")
    if menge_a <= menge_b or menge_b <= menge_a:
        kleinere, groessere = ((menge_a, menge_b) if len(menge_a) <= len(menge_b)
                               else (menge_b, menge_a))
        score = round(len(kleinere) / len(groessere), 4)
        return NamensTreffer("S2", STUFE_TREFFER, score,
                             f"Token-Teilmenge nach Normalisierung: {{{', '.join(sorted(kleinere))}}} "
                             f"⊆ {{{', '.join(sorted(groessere))}}}")
    return None


def _s3_phonetik(tokens_a: list[str], tokens_b: list[str]) -> NamensTreffer | None:
    if not tokens_a or len(tokens_a) != len(tokens_b):
        return None
    codes_a = sorted(koelner_code(t) for t in tokens_a)
    codes_b = sorted(koelner_code(t) for t in tokens_b)
    # Ein leerer Code (Eingabe ohne kodierbare Buchstaben) ist nie ein Treffer.
    if not all(codes_a) or not all(codes_b) or codes_a != codes_b:
        return None
    if len(codes_a) == 1:
        begruendung = f"phonetisch identisch nach Kölner Phonetik: {codes_a[0]} = {codes_b[0]}"
    else:
        begruendung = ("phonetisch identisch nach Kölner Phonetik je Token: "
                       f"[{', '.join(codes_a)}] = [{', '.join(codes_b)}]")
    return NamensTreffer("S3", STUFE_MOEGLICH, 1.0, begruendung)


def vergleiche_namen(a: str, b: str, schwelle: float) -> NamensTreffer | None:
    """Vergleicht `a` und `b` über S1 -> S2 -> S3 -> S4; erste Stufe gewinnt.

    `schwelle`: Mindest-Ähnlichkeit für S4 (die Skills setzen sie selbst —
    `interessenkollision-check` 0.85, `gwg-live-screening` 0.80).
    """
    norm_a, norm_b = normalisiere(a), normalisiere(b)
    tokens_a, tokens_b = tokenisiere(a), tokenisiere(b)

    # S1 — exakt nach Normalisierung.
    if norm_a and norm_b and norm_a == norm_b:
        return NamensTreffer("S1", STUFE_TREFFER, 1.0,
                             f"exakter Treffer nach Normalisierung: '{norm_a}' = '{norm_b}'")
    treffer = _s2_token_mengen(tokens_a, tokens_b) or _s3_phonetik(tokens_a, tokens_b)
    if treffer is not None:
        return treffer

    # S4 — Fuzzy: der stärkere der beiden Ähnlichkeitsmaße entscheidet.
    score_zeichen = sequenz_ratio(norm_a, norm_b)
    score_token = token_alignment_ratio(tokens_a, tokens_b)
    score = max(score_zeichen, score_token)
    if score < schwelle:
        return None
    verfahren = "Zeichenketten-Vergleich" if score_zeichen >= score_token else "Token-Alignment"
    return NamensTreffer("S4", STUFE_MOEGLICH, round(score, 4),
                         f"Ähnlichkeit {score:.2f} ≥ Schwelle {schwelle:.2f} ({verfahren})")
