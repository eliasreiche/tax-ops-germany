#!/usr/bin/env python3
"""datum — Kanonisierung von Datumsangaben (P3-Bibliothek).

Ein Datum kommt in Kanzlei-Dokumenten in vier Schreibweisen vor: ISO
(`2026-03-01`), deutsch (`01.03.2026`, auch zweistellig `01.03.26`),
ausgeschrieben (`9. Januar 2026`, `09. Januar 2026`) und — in rohem
E-Mail-Quelltext — als RFC-2822-Header (`Thu, 3 Apr 2026 14:22:05 +0200`).
Für jeden Wortlaut-Abgleich (Provenienz, Beleg-Suche) müssen alle vier auf
dieselbe Kanonform `JJJJ-MM-TT` gebracht werden — sonst gilt ein wörtlich
im Dokument stehendes Datum als „nicht belegt", nur weil die Schreibweise
abweicht.

Diese Bibliothek ist die **eine** Stelle dafür (vorher je einmal in
`aktenkopf-extraktor/executor.py`, `posteingang-ocr-verteilung/executor.py`
und `taetigkeitstext-rvg/executor.py` dupliziert).

Nur Standardbibliothek. Reine Funktionen, kein Datei-/Netzwerkzugriff.

Zweistellige Jahre: `<= 69` → 20xx, sonst 19xx (Fenster wie POSIX/`strptime`).
Ein Wert, der kein gültiges Kalenderdatum ist (31.02.), ergibt `None` — nie
ein geratenes Nachbardatum.

Bewusste Grenzen:

* Ausgeschriebene deutsche Monatsnamen werden nur mit **vierstelligem**
  Jahr erkannt (`9. Januar 2026`, nicht `9. Januar 26`) — spellte Daten mit
  zweistelligem Jahr sind in der Praxis nicht beobachtet und die
  Jahrhundert-Heuristik wäre hier weniger eindeutig als bei Ziffernformaten.
* Abkürzungen nur für die neun Monate, die ohne Mehrdeutigkeit auf ihren
  vollen Namen zurückführen (`Jan.`–`Dez.`, siehe `_MONAT_ABKUERZUNGEN`
  unten). **`Jun.`/`Jul.`** sind bewusst ausgespart: diese Abkürzungen sind in
  Kanzleikorrespondenz gebräuchlich für Namenszusätze („Junior"), eine
  automatische Monats-Deutung wäre hier eine Ratewette, kein eindeutiger
  Fund — im Zweifel gilt „nicht erkannt" statt Halluzination. `Mai` hat
  ohnehin keine kürzere Abkürzung und wird als vollständiger Monatsname
  erkannt (`1. Mai 2026` → `2026-05-01`).
* RFC-2822 wird nur als **vollständiger** Datum-Zeit-String erkannt (Datum +
  Uhrzeit + Zeitzone/Zonenname, wie ihn jeder `Date:`-Header trägt) — ein
  isoliertes `3 Apr 2026` ohne Uhrzeit ist kein gültiger RFC-2822-Header und
  wird bewusst nicht geraten (deckungsgleich mit `email.utils.parsedate_to_datetime`,
  das dieselbe Vollständigkeit verlangt).
"""
from __future__ import annotations

import datetime as _dt
import re
from email.utils import parsedate_to_datetime as _parsedate_to_datetime

# Roh-Muster (ohne Wortgrenzen) — auch für `re.fullmatch` auf einem
# Einzelwert verwendbar.
ISO_RAW = r"(\d{4})-(\d{1,2})-(\d{1,2})"
DE_RAW = r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})"

_DATUM_ISO = re.compile(r"\b" + ISO_RAW + r"\b")
_DATUM_DE = re.compile(r"(?<!\d)" + DE_RAW + r"(?!\d)")

# Deutsche Monatsnamen — hartkodiert, keine Locale-Abhängigkeit (`strptime`
# mit `%B` hängt vom System-Locale ab, das auf einem Kanzlei-Rechner nicht
# zuverlässig `de_DE` ist).
_MONATE_VOLL = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11,
    "dezember": 12,
}
# Nur die neun unzweideutigen Abkürzungen — siehe „Bewusste Grenzen" oben.
_MONAT_ABKUERZUNGEN = {
    "jan": 1, "feb": 2, "mär": 3, "apr": 4, "aug": 8, "sep": 9, "okt": 10,
    "nov": 11, "dez": 12,
}
_MONATE = {**_MONATE_VOLL, **_MONAT_ABKUERZUNGEN}
# Längere Namen zuerst, sonst matcht z. B. "Mär" schon innerhalb von "März".
_MONATSNAME_ALT = "|".join(re.escape(n) for n in
                            sorted(_MONATE, key=len, reverse=True))
MONATSNAME_RAW = (r"(\d{1,2})\.?\s+(" + _MONATSNAME_ALT + r")\.?\s+(\d{4})")
_DATUM_MONATSNAME = re.compile(r"(?<!\d)" + MONATSNAME_RAW + r"(?!\d)",
                               re.IGNORECASE)

# RFC-2822 (E-Mail-Header `Date:`) — Wochentag optional, Uhrzeit + Zone
# zwingend (siehe „Bewusste Grenzen"). Nur Standard-3-Buchstaben-Monate
# (Englisch), wie RFC 2822 sie vorschreibt.
_EN_MONAT = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
_WOCHENTAG = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)"
RFC2822_RAW = (rf"(?:{_WOCHENTAG}\s*,\s*)?\d{{1,2}}\s+{_EN_MONAT}\s+\d{{2,4}}"
               rf"\s+\d{{1,2}}:\d{{2}}(?::\d{{2}})?\s*"
               rf"(?:[+-]\d{{4}}|[A-Za-z]{{1,5}})(?:\s*\([^)()]*\))?")
_DATUM_RFC2822 = re.compile(RFC2822_RAW, re.IGNORECASE)


def norm_jahr(jahr: str) -> str:
    """Zweistelliges Jahr auf vier Stellen (`26` → `2026`, `85` → `1985`)."""
    if len(jahr) == 2:
        jj = int(jahr)
        return ("20" if jj <= 69 else "19") + jahr
    return jahr.zfill(4)


def kanon_datum(jahr: str, monat: str, tag: str) -> str | None:
    """Kanonisiert ein Datum auf `JJJJ-MM-TT`; None, wenn kein gültiges Kalenderdatum."""
    j = norm_jahr(jahr)
    try:
        _dt.date(int(j), int(monat), int(tag))
    except ValueError:
        return None
    return f"{int(j):04d}-{int(monat):02d}-{int(tag):02d}"


def kanon_monatsname(tag: str, monatsname: str, jahr: str) -> str | None:
    """Kanonisiert `9. Januar 2026` / `09 Mär 2026`; None bei unbekanntem Monat
    oder ungültigem Kalenderdatum."""
    monat = _MONATE.get(monatsname.strip().lower())
    if monat is None:
        return None
    return kanon_datum(jahr, str(monat), tag)


def kanon_rfc2822(wert: str) -> str | None:
    """Kanonisiert einen vollständigen RFC-2822-Datum-Zeit-String (E-Mail-
    `Date:`-Header, z. B. `Thu, 3 Apr 2026 14:22:05 +0200`).

    Nimmt nur den Datumsanteil wie geschrieben — die Zeitzone wird nicht
    umgerechnet, nur verworfen (kein UTC-Shift über Mitternacht). None bei
    jedem Parse-Fehler (unbekannter Monatsname, ungültiger Kalendertag,
    kaputte Uhrzeit/Zone) — nie ein geratener Ersatzwert.
    """
    try:
        dt = _parsedate_to_datetime(wert.strip())
    except (ValueError, TypeError):
        return None
    return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"


def kanon_wert(wert: str) -> str | None:
    """Kanonform eines einzelnen Datumswerts: ISO, deutsches Ziffernformat,
    ausgeschriebener deutscher Monatsname oder RFC-2822-Header.

    None, wenn der Wert insgesamt keine dieser Schreibweisen ist (ein Datum
    *innerhalb* eines Satzes findet `kanons_in_zeile`).
    """
    wert = wert.strip()
    mi = re.fullmatch(ISO_RAW, wert)
    if mi:
        return kanon_datum(mi.group(1), mi.group(2), mi.group(3))
    md = re.fullmatch(DE_RAW, wert)
    if md:
        return kanon_datum(md.group(3), md.group(2), md.group(1))
    mm = re.fullmatch(MONATSNAME_RAW, wert, re.IGNORECASE)
    if mm:
        return kanon_monatsname(mm.group(1), mm.group(2), mm.group(3))
    if re.fullmatch(RFC2822_RAW, wert, re.IGNORECASE):
        return kanon_rfc2822(wert)
    return None


def kanons_in_zeile(zeile: str) -> set[str]:
    """Alle gültigen Datumsnennungen einer Zeile in Kanonform (alle vier
    Schreibweisen, siehe Modul-Docstring)."""
    res: set[str] = set()
    for m in _DATUM_ISO.finditer(zeile):
        k = kanon_datum(m.group(1), m.group(2), m.group(3))
        if k:
            res.add(k)
    for m in _DATUM_DE.finditer(zeile):
        k = kanon_datum(m.group(3), m.group(2), m.group(1))
        if k:
            res.add(k)
    for m in _DATUM_MONATSNAME.finditer(zeile):
        k = kanon_monatsname(m.group(1), m.group(2), m.group(3))
        if k:
            res.add(k)
    for m in _DATUM_RFC2822.finditer(zeile):
        k = kanon_rfc2822(m.group(0))
        if k:
            res.add(k)
    return res
