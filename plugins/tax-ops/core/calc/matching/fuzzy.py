"""fuzzy — Ähnlichkeits-Maße für Namensvergleich (P3-Bibliothek).

Zwei komplementäre Maße, beide nur Standardbibliothek (`difflib`):

  - `sequenz_ratio()` — Zeichenketten-Ähnlichkeit über den gesamten String
    (`difflib.SequenceMatcher.ratio()`), gut für Tippfehler/Schreibvarianten
    innerhalb eines Wortes ("Mustermann" vs. "Mustaermann").
  - `token_alignment_ratio()` — tokenbasierter Vergleich mit bestem
    Token-Alignment: jedes Token der kürzeren Liste wird höchstens einem
    Token der anderen Liste zugeordnet (1:1), das Alignment wird gierig nach
    absteigendem Paar-Score gebildet. Robuster als `sequenz_ratio()` bei
    unterschiedlicher Wortreihenfolge oder wenn nur eines von mehreren
    Tokens einen Tippfehler enthält ("Auto Müller GmbH" vs. "Automüler
    GmbH" o. Ä.).

Beide Funktionen liefern einen Score in [0.0, 1.0]; sie treffen selbst keine
Schwellenwert-Entscheidung (S4 "moeglicher_treffer" ab welchem Wert) — das
ist Sache des aufrufenden Matching-Executors (Deterministik-Grenze, P3: der
Executor entscheidet, nicht diese Bibliothek und nicht das Modell).

Grenzen (dokumentiert):

  - `token_alignment_ratio()` bildet das Alignment **gierig** (höchster
    Paar-Score zuerst), nicht über ein exaktes Optimierungsverfahren (z. B.
    ungarische Methode). Für die kurzen Namens-Tokenlisten dieses Skills
    (typischerweise 1–5 Tokens je Partei) ist der Unterschied zum globalen
    Optimum in der Praxis vernachlässigbar; bei sehr langen Tokenlisten kann
    die gierige Zuordnung suboptimal sein.
"""
from __future__ import annotations

import difflib
from typing import Sequence


def sequenz_ratio(a: str, b: str) -> float:
    """Zeichenketten-Ähnlichkeit über den gesamten String, Bereich [0.0, 1.0]."""
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def token_alignment_ratio(tokens_a: Sequence[str], tokens_b: Sequence[str]) -> float:
    """Bestes 1:1-Token-Alignment zwischen zwei Token-Listen, Bereich [0.0, 1.0].

    Baut die Paar-Score-Matrix (`sequenz_ratio` je Tokenpaar), ordnet
    Tokenpaare danach gierig nach absteigendem Score zu (jedes Token
    höchstens einmal verbraucht) und normiert die Summe der zugeordneten
    Scores auf die Länge der **längeren** Tokenliste — nicht zugeordnete
    Tokens (bei unterschiedlicher Tokenanzahl) zählen damit implizit als 0
    zum Gesamtscore.
    """
    if not tokens_a or not tokens_b:
        return 0.0

    paare = [
        (sequenz_ratio(ta, tb), i, j)
        for i, ta in enumerate(tokens_a)
        for j, tb in enumerate(tokens_b)
    ]
    paare.sort(key=lambda p: p[0], reverse=True)

    verbraucht_a: set[int] = set()
    verbraucht_b: set[int] = set()
    summe = 0.0
    for score, i, j in paare:
        if i in verbraucht_a or j in verbraucht_b:
            continue
        verbraucht_a.add(i)
        verbraucht_b.add(j)
        summe += score

    laenge = max(len(tokens_a), len(tokens_b))
    return summe / laenge if laenge else 0.0
