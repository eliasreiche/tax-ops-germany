#!/usr/bin/env python3
"""provenienz — Beleg-Prüfung modellgenerierter Werte gegen die Quelldateien (P3).

Die Anti-Halluzinations-Disziplin des Repos (CONVENTIONS.md) verlangt, dass
jeder kritische Wert eines modellerzeugten Entwurfs — Datum, Aktenzeichen,
Zitat, Geldbetrag — nach definierter Normalisierung **wörtlich** in
mindestens einer Quelldatei vorkommt. Diese Bibliothek ist die eine Stelle,
die das prüft (vorher je einmal in `aktenkopf-extraktor/executor.py` und
`posteingang-ocr-verteilung/executor.py`).

Aufteilung der Zuständigkeit:

  * **Skill-Executor**: sammelt die kritischen Werte aus *seiner* Struktur
    (`sammle_kritische_werte()` — welches Feld ist kritisch, ist skill-
    spezifisch) und liefert sie als `[{"pfad", "typ", "wert"}]`.
  * **Diese Bibliothek**: normalisiert Wert und Quellzeile nach Typ, sucht
    den ersten Beleg und vergibt `belegt`/`nicht_belegt` samt Fundstelle.

Ein **Typ** ist ein Paar von Funktionen:

    (wert_kanon, zeilen_kanon)

`wert_kanon(wert) -> str | None` bringt den zu prüfenden Wert in Kanonform
(None = nicht prüfbar ⇒ nicht belegt), `zeilen_kanon(zeile)` bringt eine
Quellzeile in eine Form, in der `ziel in zeilen_kanon(zeile)` der Beleg-Test
ist — das funktioniert sowohl für Mengen (Datum: Menge aller Datumswerte der
Zeile) als auch für Strings (Teilstring-Suche in der normalisierten Zeile).

`STANDARD_TYPEN` deckt Datum, Aktenzeichen und Zitat ab. Weitere Typen
übergibt der Aufrufer als Dict, z. B. der aktenkopf-extraktor:

    TYPEN = STANDARD_TYPEN | {
        "geld": (_geld_kanon, _geld_kanons_in_zeile),
        "email": (lambda w: w.strip().lower() or None, str.lower),
        "telefon": (lambda w: _tel_norm(w) or None, _tel_norm),
        "iban": (lambda w: _iban_norm(w) or None, _iban_norm),
    }

Nur Standardbibliothek. Kein Netzwerkzugriff, kein Datei-I/O (die Quellen
werden als bereits gelesene Zeilenlisten übergeben).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Callable, Container

# datum liegt in core/calc/ — Pfad robust einhängen (gleiches Muster wie
# core/calc/fristen/rechner.py für feiertage).
_CALC_DIR = Path(__file__).resolve().parents[1] / "calc"
if str(_CALC_DIR) not in sys.path:
    sys.path.insert(0, str(_CALC_DIR))

from datum import kanon_wert as _datum_kanon_wert  # noqa: E402
from datum import kanons_in_zeile as _datum_kanons_in_zeile  # noqa: E402

STATUS_BELEGT = "belegt"
STATUS_NICHT_BELEGT = "nicht_belegt"

# (wert_kanon, zeilen_kanon) — siehe Modul-Docstring.
Normalisierer = tuple[Callable[[str], "str | None"], Callable[[str], Container[str]]]


def ws_collapse(s: str) -> str:
    """Mehrfach-Whitespace zu einem Leerzeichen, Ränder getrimmt.

    Damit trifft ein Aktenzeichen/Zitat auch dann, wenn OCR oder Umbruch die
    Abstände verändert haben.
    """
    return re.sub(r"\s+", " ", s).strip()


def _ws_kanon(wert: str) -> str | None:
    return ws_collapse(wert) or None


STANDARD_TYPEN: dict[str, Normalisierer] = {
    "datum": (_datum_kanon_wert, _datum_kanons_in_zeile),
    "aktenzeichen": (_ws_kanon, ws_collapse),
    "zitat": (_ws_kanon, ws_collapse),
}


def kanon_ziel(wert: str, typ: str,
               typen: dict[str, Normalisierer] | None = None) -> str | None:
    """Kanonform des gesuchten Werts; None = unbekannter Typ oder nicht prüfbar."""
    eintrag = (typen or STANDARD_TYPEN).get(typ)
    return eintrag[0](wert) if eintrag else None


def zeile_belegt(zeile: str, typ: str, ziel: str,
                 typen: dict[str, Normalisierer] | None = None) -> bool:
    """True, wenn `ziel` (bereits kanonisiert) in dieser Quellzeile steht."""
    eintrag = (typen or STANDARD_TYPEN).get(typ)
    return ziel in eintrag[1](zeile) if eintrag else False


def finde_beleg(wert: str, typ: str, quellen: list[tuple[str, list[str]]],
                typen: dict[str, Normalisierer] | None = None) -> dict[str, Any] | None:
    """Sucht den ersten Beleg für `wert` in den Quelldateien. Rückgabe:
    Fundstelle `{datei, zeile, zitat}` oder None (nicht belegt).

    `quellen`: `[(dateiname, zeilen)]` — Zeilen ohne Zeilenumbruch.
    """
    ziel = kanon_ziel(wert, typ, typen)
    if not ziel:
        return None
    for datei, zeilen in quellen:
        for i, zeile in enumerate(zeilen, start=1):
            if zeile_belegt(zeile, typ, ziel, typen):
                return {"datei": datei, "zeile": i, "zitat": zeile.strip()}
    return None


def pruefe_provenienz(werte: list[dict[str, str]],
                      quellen: list[tuple[str, list[str]]],
                      typen: dict[str, Normalisierer] | None = None
                      ) -> list[dict[str, Any]]:
    """Prüft die vom Skill gesammelten kritischen Werte gegen die Quellen.

    `werte`: `[{"pfad", "typ", "wert"}]` (Reihenfolge bleibt erhalten).
    Rückgabe je Wert: Pfad/Typ/Wert plus `status`, `fundstelle`, `begruendung`.
    """
    ergebnisse: list[dict[str, Any]] = []
    for kw in werte:
        beleg = finde_beleg(kw["wert"], kw["typ"], quellen, typen)
        if beleg is not None:
            ergebnisse.append({
                "pfad": kw["pfad"], "typ": kw["typ"], "wert": kw["wert"],
                "status": STATUS_BELEGT, "fundstelle": beleg,
                "begruendung": f"wörtlich in Quelle gefunden (Normalisierung: {kw['typ']})",
            })
        else:
            ergebnisse.append({
                "pfad": kw["pfad"], "typ": kw["typ"], "wert": kw["wert"],
                "status": STATUS_NICHT_BELEGT, "fundstelle": None,
                "begruendung": ("kein Vorkommen in den Quelldateien "
                                f"(Normalisierung: {kw['typ']}) — Wert streichen "
                                "oder als Lücke ausweisen"),
            })
    return ergebnisse


# --------------------------------------------------------------------------
# Lücken-Disziplin (Schema-Prüfung der Skills, gemeinsame Bausteine)
# --------------------------------------------------------------------------

def leer(v: Any) -> bool:
    """True bei None oder leerem/nur-Whitespace-String."""
    return v is None or (isinstance(v, str) and v.strip() == "")


def nichtleer(v: Any) -> bool:
    """True nur bei einem String mit Inhalt (kein `not leer()`: Zahlen/dicts
    sind hier weder leer noch ein prüfbarer Wert)."""
    return isinstance(v, str) and v.strip() != ""


def luecken_felder(dokument: dict[str, Any]) -> set[str]:
    """Feldnamen, die im `luecken`-Array explizit als Lücke geführt werden."""
    felder: set[str] = set()
    luecken = dokument.get("luecken")
    if isinstance(luecken, list):
        for eintrag in luecken:
            if isinstance(eintrag, dict) and isinstance(eintrag.get("feld"), str):
                felder.add(eintrag["feld"].strip())
    return felder
