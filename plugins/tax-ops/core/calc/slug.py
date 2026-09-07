#!/usr/bin/env python3
"""slug — Dateinamens-Slug für Ablage-Konventionen (P2).

Eine Regel, zwei Nutzer: `email-akten-zuordnung` bildet den Betreff-Slug für
`posteingang/JJJJ-MM-TT-<slug>.eml`, `posteingang-ocr-verteilung` den
Absender-Slug für `posteingang/JJJJ-MM-TT_<az>_<slug>/`. Vorher zweimal
identisch implementiert.

Nur Standardbibliothek, reine Funktion.
"""
from __future__ import annotations

import re

SLUG_MAX_LEN = 60

_UMLAUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                         "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})
_NICHT_ERLAUBT_RE = re.compile(r"[^a-z0-9]+")


def slug(text: str, fallback: str) -> str:
    """Umlaute transliterieren, kleinschreiben, alles außer a-z/0-9 zu '-'
    kollabieren, Ränder trimmen, auf `SLUG_MAX_LEN` kürzen.

    Bleibt nichts übrig (leerer/fehlender Text), gilt `fallback` — es wird nie
    ein Titel erfunden.
    """
    basis = (text or "").translate(_UMLAUT).lower()
    gekuerzt = _NICHT_ERLAUBT_RE.sub("-", basis).strip("-")[:SLUG_MAX_LEN]
    return gekuerzt.rstrip("-") or fallback
