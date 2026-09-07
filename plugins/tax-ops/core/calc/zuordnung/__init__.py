"""zuordnung — Dokument-Metadaten -> Mandats-Kandidaten (P3-Bibliothek).

Öffentliche API für die E-Mail-/Posteingang-Akten-Zuordnung, genutzt von
`plugins/legal-ops/skills/email-akten-zuordnung/executor.py` und künftig
von Skill #14 `posteingang-ocr-verteilung` (Welle 4). Reine
Standardbibliothek (nutzt intern `core/calc/matching`), kein
Netzwerkzugriff, keine Persistierung.

  - `az` — Aktenzeichen-Normalisierung und -Suche (Stufe Z0).
  - `parteisuche` — Parteiname-in-Text-Suche (Stufen Z1-Z4) sowie die
    Nachname-Bausteine der Stufe Z2N (`nachname()`,
    `nachname_in_personen_position()`).
  - `zuordnung` — kombiniert beides zu `finde_kandidaten()` über die Stufen
    Z0, Z1-Z4 und Z2N (Nachname + Korroboration, siehe dortigen Docstring).

Stufen-Leiter insgesamt: Z0 (Az) > Z1/Z2 (Vollname wörtlich) > Z2N
(Nachname + Korroboration) > Z3/Z4 (Phonetik/Fuzzy). Z0-Z2 sind `treffer`,
Z2N/Z3/Z4 sind `moeglicher_treffer`.
"""
from __future__ import annotations

from .az import az_gefunden_in_text, normalisiere_az
from .parteisuche import (
    SCHWELLE_MOEGLICH_DEFAULT,
    STUFE_MOEGLICH,
    STUFE_TREFFER,
    ParteiTreffer,
    nachname,
    nachname_in_personen_position,
    suche_name_in_text,
)
from .zuordnung import (
    STUFE_NACHNAME,
    Dokument,
    Kandidat,
    Mandat,
    finde_kandidaten,
    finde_kandidaten_mit_hinweisen,
    vergleiche_dokument_mandat,
)

__all__ = [
    "normalisiere_az",
    "az_gefunden_in_text",
    "STUFE_TREFFER",
    "STUFE_MOEGLICH",
    "STUFE_NACHNAME",
    "SCHWELLE_MOEGLICH_DEFAULT",
    "ParteiTreffer",
    "nachname",
    "nachname_in_personen_position",
    "suche_name_in_text",
    "Dokument",
    "Mandat",
    "Kandidat",
    "finde_kandidaten",
    "finde_kandidaten_mit_hinweisen",
    "vergleiche_dokument_mandat",
]
