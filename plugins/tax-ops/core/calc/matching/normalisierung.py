"""normalisierung — Namens-Normalisierung für Fuzzy-Matching (P3-Bibliothek).

Vereinheitlicht Partei-Namen (natürliche und juristische Personen) auf eine
vergleichbare Form, damit Schreibweisen-Varianten ("Müller GmbH" / "MÜLLER
GMBH" / "Mueller GmbH.") als gleich erkannt werden. Reine Textverarbeitung,
kein Rechnen, kein Netzwerkzugriff — Standardbibliothek only.

Normalisierungs-Pipeline (in dieser Reihenfolge, siehe `normalisiere()`):

  1. Kleinschreibung.
  2. Umlaut-/ß-Transliteration: ä→ae, ö→oe, ü→ue, ß→ss (auch Großschreibung,
     die durch Schritt 1 bereits auf ä/ö/ü/ß reduziert wurde).
  3. Titel-Stripping (Personen): bekannte akademische Titel/Grade werden als
     eigene Tokens entfernt, siehe `_TITEL_PATTERNS`.
  4. Rechtsform-Stripping (juristische Personen): bekannte Rechtsform-Zusätze
     werden entfernt, siehe `_RECHTSFORM_PATTERNS`. Mehrwort-Formen
     ("GmbH & Co. KG") werden vor ihren Einzel-Bestandteilen geprüft, damit
     sie als Ganzes erkannt werden, statt in Reste zu zerfallen.
  5. Verbleibende Interpunktion wird durch Leerzeichen ersetzt, mehrfache
     Leerzeichen werden zusammengefasst, führende/folgende Leerzeichen
     entfernt.

Der Wortreihenfolge-Vergleich ("Auto Müller GmbH" ↔ "Müller Auto GmbH")
läuft nicht über eine Sortier-Stufe dieser Pipeline, sondern über den
Token-**Mengen**-Vergleich in `matching/vergleich.py` (Stufe S2).

Bewusste Grenzen (siehe auch schema/README.md des Skills):

  - Rechtsform-/Titel-Stripping arbeitet tokenbasiert (Wortgrenzen), nicht
    positionsbasiert. Ein Namensbestandteil, der zufällig mit einer bekannten
    Rechtsform oder einem Titel identisch ist (z. B. eine Person mit
    Nachnamen "Se" oder "Mag"), wird ebenfalls gestrippt. Seltener Randfall,
    hier dokumentiert statt stillschweigend in Kauf genommen.
  - Rechtsform-Stripping allein ist **kein** Namens-Match: "Müller GmbH" und
    "Schulze GmbH" bleiben nach Stripping "mueller" und "schulze" — eindeutig
    verschieden. Der Matching-Executor darf einen Treffer nie allein aus der
    gemeinsamen Rechtsform ableiten (siehe False-Positive-Tests des Skills).
  - Die Titel-/Rechtsform-Listen sind kuratiert, nicht erschöpfend
    (erweiterbar per Pull Request).
"""
from __future__ import annotations

import re

# --------------------------------------------------------------------------
# Rechtsform-Liste (Datenliste, dokumentiert)
# --------------------------------------------------------------------------
# Reihenfolge ist bedeutsam: Mehrwort-Formen zuerst, damit sie als Ganzes
# erkannt werden (sonst würde z. B. "GmbH & Co. KG" in "GmbH" + Rest + "KG"
# zerfallen und nur "GmbH" träfe, "KG" bliebe als eigenes, sinnloses Token
# stehen). Alle Muster arbeiten auf bereits kleingeschriebenem,
# transliteriertem Text (ä→ae usw., siehe Modul-Docstring).

_RECHTSFORM_PATTERNS: tuple[str, ...] = (
    r"\bgmbh\s*(?:&|und)\s*co\.?\s*kg\b",
    r"\bpartg\s*mbb\b",
    # Kein abschließendes \b: ')' ist ein Nicht-Wortzeichen, ein \b davor
    # verlangt einen \w/\W-Übergang, den es am Wort-/Stringende nach ')'
    # nie gibt — die Regex würde sonst nie greifen und "ug" allein bliebe
    # stehen, während "(haftungsbeschraenkt)" unangetastet zurückbleibt.
    r"\bug\s*\(\s*haftungsbeschraenkt\s*\)",
    r"\bgmbh\b",
    r"\bmbh\b",
    r"\bag\b",
    r"\bkg\b",
    r"\bohg\b",
    r"\bgbr\b",
    r"\bug\b",
    r"\be\.\s*v\.?\b",
    r"\be\.\s*k\.?\b",
    r"\bpartg\b",
    r"\bse\b",
    r"\bstiftung\b",
)
_RECHTSFORM_RE = re.compile("|".join(_RECHTSFORM_PATTERNS))

# --------------------------------------------------------------------------
# Titel-Liste (Personen, Datenliste, dokumentiert)
# --------------------------------------------------------------------------
# Kuratierte, nicht erschöpfende Auswahl akademischer Titel/Grade, wie sie in
# Mandanten-/Gegnerlisten deutscher Kanzleien typischerweise vorkommen.
# Mehrwort-/zusammengesetzte Formen zuerst (gleiches Prinzip wie oben).

_TITEL_PATTERNS: tuple[str, ...] = (
    r"\bdr\.?\s*dr\.?\s*h\.?\s*c\.?\b",
    r"\bdr\.?\s*h\.?\s*c\.?\b",
    r"\bdr\.?\s*med\.?\b",
    r"\bdr\.?\s*jur\.?\b",
    r"\bdr\.?\s*rer\.?\s*nat\.?\b",
    r"\bprof\.?\s*dr\.?\b",
    r"\bdipl\.?-?\s*ing\.?\b",
    r"\bdipl\.?-?\s*kfm\.?\b",
    r"\bdipl\.?-?\s*volksw\.?\b",
    r"\bdipl\.?-?\s*oec\.?\b",
    r"\bdr\.?\b",
    r"\bprof\.?\b",
    r"\bmag\.?\b",
    r"\bing\.?\b",
    r"\bll\.?\s*m\.?\b",
)
_TITEL_RE = re.compile("|".join(_TITEL_PATTERNS))

_UMLAUT_TABELLE = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
})

_NICHT_ALPHANUMERISCH_RE = re.compile(r"[^a-z0-9\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def _transliteriere(text: str) -> str:
    """Kleinschreibung + Umlaut-/ß-Transliteration (Schritte 1+2)."""
    return text.lower().translate(_UMLAUT_TABELLE)


def normalisiere(text: str) -> str:
    """Führt die vollständige Normalisierungs-Pipeline aus (siehe Modul-Docstring).

    Leere/nur-Whitespace-Eingaben ergeben einen leeren String.
    """
    if not text:
        return ""
    arbeitstext = _transliteriere(text)
    arbeitstext = _TITEL_RE.sub(" ", arbeitstext)
    arbeitstext = _RECHTSFORM_RE.sub(" ", arbeitstext)
    arbeitstext = _NICHT_ALPHANUMERISCH_RE.sub(" ", arbeitstext)
    arbeitstext = _WHITESPACE_RE.sub(" ", arbeitstext).strip()
    return arbeitstext


def tokenisiere(text: str) -> list[str]:
    """Normalisiert und zerlegt in Tokens (whitespace-getrennt)."""
    normalisiert = normalisiere(text)
    return normalisiert.split() if normalisiert else []
