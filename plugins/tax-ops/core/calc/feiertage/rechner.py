#!/usr/bin/env python3
"""feiertage — deterministischer Feiertags-Rechner (P3).

Gesetzliche Feiertage aller 16 Bundesländer, für beliebige Jahre berechnet —
keine hartkodierten Jahres-Tabellen. Die beweglichen Feiertage werden über die
Gaußsche Osterformel (in der erweiterten, säkularkorrekten Fassung nach
Butcher/Meeus für den gregorianischen Kalender) aus dem Ostersonntag abgeleitet.

Gebraucht wird das für die Fristberechnung: Nach § 193 BGB / § 222 Abs. 2 ZPO
verschiebt sich ein Fristende, das auf einen Sonnabend, Sonntag oder einen
**am Fristende-Ort** staatlich anerkannten allgemeinen Feiertag fällt, auf den
nächsten Werktag. Welche Feiertage zählen, richtet sich nach dem Bundesland —
deshalb ist dieses Modul nach Land parametrisiert.

Ehrlichkeits-Grenze (Anti-Halluzination, CONVENTIONS.md):

* **Teilgebietliche Feiertage** werden nie stillschweigend angenommen oder
  weggelassen, sondern mit ``geltung == "teilgebietlich"`` gekennzeichnet:
  - Bayern: Mariä Himmelfahrt (15.08.) nur in Gemeinden mit überwiegend
    katholischer Bevölkerung; Augsburger Hohes Friedensfest (08.08.) nur im
    Stadtgebiet Augsburg.
  - Sachsen: Fronleichnam nur in bestimmten, per Rechtsverordnung festgelegten
    katholisch geprägten Gemeinden (u. a. im sorbischen Siedlungsgebiet).
  - Thüringen: Fronleichnam nur in Gemeinden mit überwiegend katholischer
    Bevölkerung (u. a. Landkreis Eichsfeld).
  ``ist_feiertag()`` liefert für solche Tage ``gesetzlich=False`` (nicht
  landesweit) **plus** ``teilgebietlich=True`` mit Warnung — die Entscheidung
  für die konkrete Gemeinde bleibt beim Anwender.
* **Zeitliche Geltung**: Die kodierten Regeln entsprechen der aktuellen
  Gesetzeslage (Stand siehe ``STAND``). Jahresabhängige Einführungen sind
  abgebildet (Reformationstag in HB/HH/NI/SH ab 2018, Weltkindertag in TH ab
  2019, Frauentag in BE ab 2019 und MV ab 2023, einmalige Feiertage 2017/2020/
  2025). Für Jahre **vor 1995** ist der Bestand historisch abweichend (u. a.
  war der Buß- und Bettag bis 1994 in fast allen Ländern gesetzlicher
  Feiertag) — dafür gibt ``jahres_hinweise()`` eine Warnung aus, statt falsche
  Sicherheit vorzutäuschen.

Nur Standardbibliothek. Kein Netzwerkzugriff.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field, asdict
from typing import Any

#: Stand der hier kodierten Feiertagsregeln (Rechtslage, nicht Code-Datum).
STAND = "2026-07-11"

#: Die 16 Bundesländer (ISO-3166-2-DE-Kürzel ohne Präfix).
BUNDESLAENDER = {
    "BW": "Baden-Württemberg",
    "BY": "Bayern",
    "BE": "Berlin",
    "BB": "Brandenburg",
    "HB": "Bremen",
    "HH": "Hamburg",
    "HE": "Hessen",
    "MV": "Mecklenburg-Vorpommern",
    "NI": "Niedersachsen",
    "NW": "Nordrhein-Westfalen",
    "RP": "Rheinland-Pfalz",
    "SL": "Saarland",
    "SN": "Sachsen",
    "ST": "Sachsen-Anhalt",
    "SH": "Schleswig-Holstein",
    "TH": "Thüringen",
}

GELTUNG_BUNDESWEIT = "bundesweit"
GELTUNG_LANDESWEIT = "landesweit"
GELTUNG_TEILGEBIETLICH = "teilgebietlich"

# Gültigkeitsbereich der Osterformel (gregorianischer Kalender).
_JAHR_MIN = 1583
_JAHR_MAX = 4099

# Vor 1995 weicht der Feiertagsbestand historisch ab (Buß- und Bettag u. a.).
_JAHR_VERLAESSLICH_AB = 1995


@dataclass(frozen=True)
class Feiertag:
    """Ein einzelner Feiertag mit ehrlicher Geltungs-Kennzeichnung."""
    datum: _dt.date
    name: str
    geltung: str                      # bundesweit | landesweit | teilgebietlich
    hinweis: str | None = None        # nur bei teilgebietlich/einmalig gefüllt

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["datum"] = self.datum.isoformat()
        return d


@dataclass
class FeiertagsAuskunft:
    """Ergebnis von ist_feiertag() — Executor-Ergebnis (P3)."""
    datum: _dt.date
    bundesland: str
    gesetzlich: bool                  # landesweit gesetzlicher Feiertag?
    name: str | None = None
    teilgebietlich: bool = False      # Feiertag nur in Teilen des Landes?
    teilgebiet_name: str | None = None
    warnungen: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["datum"] = self.datum.isoformat()
        return d


def _pruefe_bundesland(bundesland: str) -> str:
    kuerzel = bundesland.strip().upper()
    if kuerzel not in BUNDESLAENDER:
        raise ValueError(
            f"unbekanntes Bundesland-Kürzel: {bundesland!r} "
            f"(erlaubt: {', '.join(sorted(BUNDESLAENDER))})")
    return kuerzel


def _pruefe_jahr(jahr: int) -> None:
    if not (_JAHR_MIN <= jahr <= _JAHR_MAX):
        raise ValueError(
            f"Jahr {jahr} außerhalb des gültigen Bereichs der gregorianischen "
            f"Osterformel ({_JAHR_MIN}–{_JAHR_MAX})")


def ostersonntag(jahr: int) -> _dt.date:
    """Ostersonntag nach der Gaußschen Osterformel (Fassung Butcher/Meeus).

    Gültig für den gregorianischen Kalender (1583–4099); enthält die
    säkularen Korrekturen, die Gauß' Grundformel für Ausnahmejahre ergänzen.
    """
    _pruefe_jahr(jahr)
    a = jahr % 19
    b = jahr // 100
    c = jahr % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    monat = (h + l - 7 * m + 114) // 31
    tag = ((h + l - 7 * m + 114) % 31) + 1
    return _dt.date(jahr, monat, tag)


def buss_und_bettag(jahr: int) -> _dt.date:
    """Buß- und Bettag: der Mittwoch vor dem 23. November.

    Seit 1995 nur noch in Sachsen gesetzlicher Feiertag.
    """
    _pruefe_jahr(jahr)
    nov23 = _dt.date(jahr, 11, 23)
    versatz = (nov23.weekday() - 2) % 7  # 2 = Mittwoch
    if versatz == 0:
        versatz = 7                       # 23.11. ist selbst Mittwoch → Vorwoche
    return nov23 - _dt.timedelta(days=versatz)


# --------------------------------------------------------------------------
# Feiertagslisten
# --------------------------------------------------------------------------

def _bundesweite(jahr: int) -> list[Feiertag]:
    ostern = ostersonntag(jahr)
    tage = [
        Feiertag(_dt.date(jahr, 1, 1), "Neujahr", GELTUNG_BUNDESWEIT),
        Feiertag(ostern - _dt.timedelta(days=2), "Karfreitag", GELTUNG_BUNDESWEIT),
        Feiertag(ostern + _dt.timedelta(days=1), "Ostermontag", GELTUNG_BUNDESWEIT),
        Feiertag(_dt.date(jahr, 5, 1), "Tag der Arbeit", GELTUNG_BUNDESWEIT),
        Feiertag(ostern + _dt.timedelta(days=39), "Christi Himmelfahrt", GELTUNG_BUNDESWEIT),
        Feiertag(ostern + _dt.timedelta(days=50), "Pfingstmontag", GELTUNG_BUNDESWEIT),
        Feiertag(_dt.date(jahr, 10, 3), "Tag der Deutschen Einheit", GELTUNG_BUNDESWEIT),
        Feiertag(_dt.date(jahr, 12, 25), "1. Weihnachtstag", GELTUNG_BUNDESWEIT),
        Feiertag(_dt.date(jahr, 12, 26), "2. Weihnachtstag", GELTUNG_BUNDESWEIT),
    ]
    if jahr == 2017:
        # 500. Reformationsjubiläum: einmalig in allen 16 Ländern Feiertag.
        tage.append(Feiertag(_dt.date(2017, 10, 31),
                             "Reformationstag", GELTUNG_BUNDESWEIT,
                             hinweis="einmalig bundesweit 2017 (500. Reformationsjubiläum)"))
    return tage


def _landesweite(jahr: int, land: str) -> list[Feiertag]:
    ostern = ostersonntag(jahr)
    fronleichnam = ostern + _dt.timedelta(days=60)
    tage: list[Feiertag] = []

    def add(datum: _dt.date, name: str, hinweis: str | None = None) -> None:
        tage.append(Feiertag(datum, name, GELTUNG_LANDESWEIT, hinweis))

    if land in {"BW", "BY", "ST"}:
        add(_dt.date(jahr, 1, 6), "Heilige Drei Könige")
    if land == "BE" and jahr >= 2019:
        add(_dt.date(jahr, 3, 8), "Internationaler Frauentag")
    if land == "MV" and jahr >= 2023:
        add(_dt.date(jahr, 3, 8), "Internationaler Frauentag")
    if land == "BB":
        # Brandenburg zählt Oster- und Pfingstsonntag als gesetzliche Feiertage
        # (beides Sonntage — für § 193 BGB ohne eigene Wirkung, aber vollständig).
        add(ostern, "Ostersonntag")
        add(ostern + _dt.timedelta(days=49), "Pfingstsonntag")
    if land == "BE" and jahr in (2020, 2025):
        # Einmalige Feiertage: 75. bzw. 80. Jahrestag der Befreiung.
        add(_dt.date(jahr, 5, 8), "Tag der Befreiung",
            hinweis=f"einmalig {jahr} (nur Berlin)")
    if land in {"BW", "BY", "HE", "NW", "RP", "SL"}:
        add(fronleichnam, "Fronleichnam")
    if land == "SL":
        add(_dt.date(jahr, 8, 15), "Mariä Himmelfahrt")
    if land == "TH" and jahr >= 2019:
        add(_dt.date(jahr, 9, 20), "Weltkindertag")
    if land in {"BB", "MV", "SN", "ST", "TH"} and jahr != 2017:
        add(_dt.date(jahr, 10, 31), "Reformationstag")
    if land in {"HB", "HH", "NI", "SH"} and jahr >= 2018 and jahr != 2017:
        add(_dt.date(jahr, 10, 31), "Reformationstag")
    if land in {"BW", "BY", "NW", "RP", "SL"}:
        add(_dt.date(jahr, 11, 1), "Allerheiligen")
    if land == "SN":
        add(buss_und_bettag(jahr), "Buß- und Bettag")
    return tage


def _teilgebietliche(jahr: int, land: str) -> list[Feiertag]:
    ostern = ostersonntag(jahr)
    fronleichnam = ostern + _dt.timedelta(days=60)
    tage: list[Feiertag] = []
    if land == "BY":
        tage.append(Feiertag(
            _dt.date(jahr, 8, 8), "Augsburger Hohes Friedensfest",
            GELTUNG_TEILGEBIETLICH,
            hinweis="nur im Stadtgebiet Augsburg gesetzlicher Feiertag"))
        tage.append(Feiertag(
            _dt.date(jahr, 8, 15), "Mariä Himmelfahrt",
            GELTUNG_TEILGEBIETLICH,
            hinweis="nur in bayerischen Gemeinden mit überwiegend katholischer "
                    "Bevölkerung gesetzlicher Feiertag — konkrete Gemeinde prüfen"))
    if land == "SN":
        tage.append(Feiertag(
            fronleichnam, "Fronleichnam", GELTUNG_TEILGEBIETLICH,
            hinweis="in Sachsen nur in bestimmten, per Rechtsverordnung "
                    "festgelegten katholisch geprägten Gemeinden gesetzlicher "
                    "Feiertag — konkrete Gemeinde prüfen"))
    if land == "TH":
        tage.append(Feiertag(
            fronleichnam, "Fronleichnam", GELTUNG_TEILGEBIETLICH,
            hinweis="in Thüringen nur in Gemeinden mit überwiegend katholischer "
                    "Bevölkerung gesetzlicher Feiertag — konkrete Gemeinde prüfen"))
    return tage


def feiertage(jahr: int, bundesland: str,
              mit_teilgebietlichen: bool = True) -> list[Feiertag]:
    """Alle gesetzlichen Feiertage in `bundesland` für `jahr`, sortiert.

    Teilgebietliche Feiertage sind enthalten (``mit_teilgebietlichen=True``,
    Default) und über ``geltung == "teilgebietlich"`` + ``hinweis`` ehrlich
    gekennzeichnet — sie gelten NICHT landesweit. Fällt ein landesweiter und
    ein bundesweiter Feiertag auf dasselbe Datum (z. B. Christi Himmelfahrt am
    1. Mai 2008), bleiben beide Einträge erhalten.
    """
    _pruefe_jahr(jahr)
    land = _pruefe_bundesland(bundesland)
    tage = _bundesweite(jahr) + _landesweite(jahr, land)
    if mit_teilgebietlichen:
        tage += _teilgebietliche(jahr, land)
    return sorted(tage, key=lambda f: (f.datum, f.geltung, f.name))


def jahres_hinweise(jahr: int, bundesland: str) -> list[str]:
    """Warnungen zur Verlässlichkeit der Regeln für dieses Jahr/Land (ehrlich
    ausgewiesene Lücken statt stillschweigender Annahmen)."""
    land = _pruefe_bundesland(bundesland)
    hinweise: list[str] = []
    if jahr < _JAHR_VERLAESSLICH_AB:
        hinweise.append(
            f"Feiertagsbestand vor {_JAHR_VERLAESSLICH_AB} historisch abweichend "
            "(u. a. Buß- und Bettag bis 1994 in fast allen Ländern gesetzlicher "
            "Feiertag) — hier ist die heutige Rechtslage kodiert, Ergebnisse "
            "für Altjahre nicht verlässlich.")
    teil = _teilgebietliche(jahr, land)
    if teil:
        namen = ", ".join(f"{f.name} ({f.datum:%d.%m.})" for f in teil)
        hinweise.append(
            f"{BUNDESLAENDER[land]} hat teilgebietliche Feiertage ({namen}) — "
            "sie gelten nicht landesweit; bei Fristen um diese Tage die "
            "konkrete Gemeinde prüfen.")
    return hinweise


def ist_feiertag(datum: _dt.date, bundesland: str) -> FeiertagsAuskunft:
    """Ist `datum` ein gesetzlicher Feiertag in `bundesland`?

    ``gesetzlich`` bejaht nur landesweit geltende Feiertage. Ist das Datum ein
    nur teilgebietlich geltender Feiertag, bleibt ``gesetzlich=False``, aber
    ``teilgebietlich=True`` mit Warnung — nie stillschweigend annehmen oder
    weglassen.
    """
    land = _pruefe_bundesland(bundesland)
    auskunft = FeiertagsAuskunft(datum=datum, bundesland=land, gesetzlich=False)

    for f in feiertage(datum.year, land, mit_teilgebietlichen=True):
        if f.datum != datum:
            continue
        if f.geltung == GELTUNG_TEILGEBIETLICH:
            auskunft.teilgebietlich = True
            auskunft.teilgebiet_name = f.name
            auskunft.warnungen.append(
                f"{f.name} am {datum:%d.%m.%Y}: {f.hinweis}")
        else:
            auskunft.gesetzlich = True
            auskunft.name = f.name if not auskunft.name else f"{auskunft.name} / {f.name}"

    if datum.year < _JAHR_VERLAESSLICH_AB:
        auskunft.warnungen.extend(jahres_hinweise(datum.year, land)[:1])
    return auskunft
