"""matching — wiederverwendbare Fuzzy-Matching-Bibliothek (P3).

Öffentliche API für Namensvergleich (natürliche und juristische Personen),
genutzt von `plugins/legal-ops/skills/interessenkollision-check/executor.py`
und `plugins/legal-ops/skills/gwg-live-screening/executor.py`
(Sanktionslisten-Abgleich). Reine Standardbibliothek, kein Netzwerkzugriff,
keine Persistierung — siehe die einzelnen Module für Regelwerk und Grenzen:

  - `normalisierung` — Normalisierung (Kleinschreibung, Umlaute, Rechtsform-/
    Titel-Stripping, Interpunktion) und Tokenisierung.
  - `koelner_phonetik` — Kölner Phonetik nach Standard-Definition.
  - `fuzzy` — Zeichenketten- und tokenbasierte Ähnlichkeitsmaße.
  - `vergleich` — die Stufen-Kaskade S1-S4 über diesen Bausteinen.
"""
from __future__ import annotations

from .fuzzy import sequenz_ratio, token_alignment_ratio
from .koelner_phonetik import code as koelner_code
from .normalisierung import normalisiere, tokenisiere
from .vergleich import (
    STUFE_MOEGLICH,
    STUFE_TREFFER,
    NamensTreffer,
    vergleiche_namen,
)

__all__ = [
    "normalisiere",
    "tokenisiere",
    "koelner_code",
    "sequenz_ratio",
    "token_alignment_ratio",
    "NamensTreffer",
    "vergleiche_namen",
    "STUFE_TREFFER",
    "STUFE_MOEGLICH",
]
