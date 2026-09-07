#!/usr/bin/env python3
"""ao_fristen — deterministische AO-Fristberechnung (P3).

Vier Bausteine, alle über den Fristen-Executor
(`executor.py`, `modus`-Feld) erreichbar:

1. **Einspruchsfrist** (§ 355 Abs. 1 AO / § 356 Abs. 2 AO) aus Bekanntgabe-
   oder Aufgabe-zur-Post-Datum, über die Bekanntgabefiktion des § 122 Abs. 2
   Nr. 1 AO, mit Fristberechnung nach §§ 187, 188 BGB (§ 108 Abs. 1 AO) und
   Wochenend-/Feiertagsverschiebung nach § 108 Abs. 3 AO.
2. **Abgabefrist** (§ 149 Abs. 2/3 AO, inkl. Art. 97 § 36 EGAO-Verlängerungen
   für VZ 2020–2024 aus `abgabefristen.json`).
3. **Vorauszahlungs-/Anmeldetermine** eines Kalenderjahres aus
   `vorauszahlungstermine.json`.
4. **Verspätungszuschlag** (§ 152 Abs. 5, 10 AO) aus festgesetzter Steuer,
   anzurechnenden Beträgen, Abgabedatum und Fristende.

Jeder Datums-/Geldwert stammt aus diesem Modul, nie vom Modell
(Deterministik-Grenze, CONVENTIONS.md P3). Nur Standardbibliothek.

**Bewusste Grenzen** (Details: SKILL.md „Nicht abgedeckt"):

* Die Dreitagesfiktion vor dem 01.01.2025 ist im Quellen-Dossier nur
  sekundär belegt — Eingaben mit `aufgabe_zur_post_datum` vor diesem Datum
  werden abgelehnt (`AONichtAbgedeckt`).
* Ob sich der Bekanntgabe-Fiktionstag selbst nach § 108 Abs. 3 AO verschiebt
  (BFH v. 14.10.2003, IX R 68/98, zur alten Dreitagesfiktion; Übertragung auf
  die seit 2025 geltende Viertagesfiktion im Dossier `[unverifiziert]`), ist
  die Option `fiktion_verschieben` — Default `False` (Dossier-Status).
* Abgabefrist für Land-/Forstwirte ist nur für VZ 2020–2024 (feste EGAO-
  Tabellenwerte) hinterlegt; ab VZ 2025 hängt sie vom individuellen
  Wirtschaftsjahresende ab (§ 149 Abs. 2 Satz 2 AO) — nicht abgedeckt.
* Verspätungszuschlag: Pflicht- vs. Ermessensfall (§ 152 Abs. 1 / Abs. 2 AO)
  wird nur als Normenhinweis ausgegeben, nicht berechnet oder gewertet
  (weder die permanente 14-/19-Monats-Grenze des Abs. 2 Nr. 1/2 noch die
  zeitweiligen EGAO-Sondergrenzen für VZ 2020–2024) — echte Subsumtion ist
  Kanzleisache. Die Ausnahme des § 152 Abs. 8 Nr. 1 AO für monatliche/
  vierteljährliche Steueranmeldungen wird als Hinweis ausgegeben; der
  Rechner ist nur für Jahressteuererklärungen vorgesehen.
* Rundung beim Verspätungszuschlag: § 152 Abs. 10 AO rundet nur den
  **Gesamtbetrag** auf volle Euro ab ("Der Verspätungszuschlag ist auf
  volle Euro abzurunden"). Bemessungsgrundlage und Monatsbetrag bleiben
  ungerundet (Decimal) — dafür gibt es keine gesetzliche Rundungsvorschrift.
"""
from __future__ import annotations

import calendar
import datetime as _dt
import json
import sys
from dataclasses import asdict, dataclass, field
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import Any

_CALC_DIR = Path(__file__).resolve().parents[1]
if str(_CALC_DIR) not in sys.path:
    sys.path.insert(0, str(_CALC_DIR))

from feiertage import BUNDESLAENDER, ist_feiertag  # noqa: E402
from feiertage import feiertage as _feiertage_liste  # noqa: E402
from rechenschritt import RechenSchritt  # noqa: E402

_HIER = Path(__file__).resolve().parent
FRISTARTEN_PFAD = _HIER / "fristarten.json"
ABGABEFRISTEN_PFAD = _HIER / "abgabefristen.json"
VORAUSZAHLUNGEN_PFAD = _HIER / "vorauszahlungstermine.json"

# Wortlautänderung "dritter" → "vierter Tag" durch das Postrechtsmodernisierungs-
# gesetz, in Kraft seit diesem Datum (Dossier Abschnitt 2, belegt).
VIERTAGESFIKTION_AB = _dt.date(2025, 1, 1)
FIKTION_TAGE = 4

# § 152 AO: https://www.gesetze-im-internet.de/ao_1977/__152.html
# geprueft_am: 2026-09-08
PFLICHT_SCHWELLE_MONATE = 14  # § 152 Abs. 2 Nr. 1 AO (Regelfall, ungewertet)
LAND_FORST_SCHWELLE_MONATE = 19  # § 152 Abs. 2 Nr. 2 AO (ungewertet)
VERSPAETUNGSZUSCHLAG_PROZENTSATZ = Decimal("0.0025")  # § 152 Abs. 5 Satz 2 AO
VERSPAETUNGSZUSCHLAG_MINDESTBETRAG = Decimal("25")     # je angefangenem Monat
VERSPAETUNGSZUSCHLAG_HOECHSTBETRAG = Decimal("25000")  # § 152 Abs. 10 AO, Höchstbetrag
SCHONFRIST_TAGE = 3  # § 240 Abs. 3 Satz 1 AO


class AOEingabeFehler(ValueError):
    """Ungültige/fehlende Eingabe → Exit 1 (CONVENTIONS dieses Skills)."""


class AONichtAbgedeckt(ValueError):
    """Eingabe bräuchte eine im Dossier nicht belegte Regel → Exit 2."""


@dataclass
class Verschiebung:
    von: _dt.date
    auf: _dt.date
    grund: str
    norm: str = "§ 108 Abs. 3 AO"

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["von"] = self.von.isoformat()
        d["auf"] = self.auf.isoformat()
        return d


# --------------------------------------------------------------------------
# Katalog-Laden (Daten, nicht Logik — P3)
# --------------------------------------------------------------------------

def lade_fristarten() -> dict[str, Any]:
    return json.loads(FRISTARTEN_PFAD.read_text(encoding="utf-8"))


def fristart_nach_id(fristart_id: str) -> dict[str, Any]:
    for f in lade_fristarten()["fristarten"]:
        if f["id"] == fristart_id:
            return f
    bekannte = ", ".join(f["id"] for f in lade_fristarten()["fristarten"])
    raise AOEingabeFehler(f"unbekannte Fristart: {fristart_id!r} (bekannt: {bekannte})")


def lade_abgabefristen() -> dict[str, Any]:
    return json.loads(ABGABEFRISTEN_PFAD.read_text(encoding="utf-8"))


def lade_vorauszahlungskatalog() -> dict[str, Any]:
    return json.loads(VORAUSZAHLUNGEN_PFAD.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Gemeinsame Werktag-Verschiebung, § 108 Abs. 3 AO
# --------------------------------------------------------------------------

_WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
               "Freitag", "Samstag", "Sonntag"]


def _wochentag(d: _dt.date) -> str:
    return _WOCHENTAGE[d.weekday()]


def _feiertagsgrund(d: _dt.date, bundesland: str, mit_teilgebietlichen: bool) -> str | None:
    gruende: list[str] = []
    if d.weekday() == 5:
        gruende.append("Sonnabend (Samstag)")
    elif d.weekday() == 6:
        gruende.append("Sonntag")
    auskunft = ist_feiertag(d, bundesland)
    if auskunft.gesetzlich:
        gruende.append(f"gesetzlicher Feiertag ({auskunft.name})")
    elif mit_teilgebietlichen and auskunft.teilgebietlich:
        gruende.append(f"teilgebietlicher Feiertag ({auskunft.teilgebiet_name})")
    return "; zugleich ".join(gruende) if gruende else None


def _verschiebe_108_3(ende: _dt.date, bundesland: str,
                      mit_teilgebietlichen: bool = False
                      ) -> tuple[_dt.date, list[Verschiebung]]:
    """§ 108 Abs. 3 AO: auf den nächstfolgenden Werktag verschieben.

    Jeder übersprungene Tag ist eine eigene Verschiebung (Kaskade
    Sa → So → Feiertag bleibt nachvollziehbar) — wie § 193 BGB / § 222 Abs. 2
    ZPO im Schwesterprojekt legal-ops-germany.
    """
    verschiebungen: list[Verschiebung] = []
    d = ende
    while True:
        grund = _feiertagsgrund(d, bundesland, mit_teilgebietlichen)
        if grund is None:
            return d, verschiebungen
        naechster = d + _dt.timedelta(days=1)
        verschiebungen.append(Verschiebung(von=d, auf=naechster, grund=grund))
        d = naechster


def _verschiebe_mit_kette(ende: _dt.date, bundesland: str, kette: list[RechenSchritt],
                          warnungen: list[str]) -> _dt.date:
    """Verschiebt `ende` nach § 108 Abs. 3 AO, hängt jede Verschiebung als
    Rechenschritt an `kette`. Prüft zusätzlich ehrlich gegen teilgebietliche
    Feiertage (Anti-Halluzination, wie core/calc/feiertage) und warnt, falls
    diese das Ergebnis ändern könnten, ohne sie stillschweigend anzunehmen
    oder wegzulassen."""
    fristende, verschiebungen = _verschiebe_108_3(ende, bundesland)
    for v in verschiebungen:
        _schritt(kette, v.norm,
                f"{v.von:%d.%m.%Y} ({_wochentag(v.von)}) ist {v.grund} in "
                f"{BUNDESLAENDER[bundesland]} — Verschiebung auf den nächsten Werktag.",
                v.auf)
    alt_ende, alt_verschiebungen = _verschiebe_108_3(ende, bundesland, mit_teilgebietlichen=True)
    if alt_ende != fristende:
        betroffene = sorted({v.grund for v in alt_verschiebungen
                             if "teilgebietlicher Feiertag" in v.grund})
        warnungen.append(
            f"Teilgebietlicher Feiertag möglich ({'; '.join(betroffene)}): gilt er am "
            f"konkreten Ort, verschiebt sich das Datum auf {alt_ende:%d.%m.%Y} "
            f"({_wochentag(alt_ende)}) statt {fristende:%d.%m.%Y} ({_wochentag(fristende)}) "
            f"— konkrete Gemeinde prüfen, beide Daten ausgewiesen.")
    return fristende


def _schritt(kette: list[RechenSchritt], norm: str, beschreibung: str,
            ergebnis: _dt.date | None) -> None:
    kette.append(RechenSchritt(
        schritt=len(kette) + 1, norm=norm, beschreibung=beschreibung,
        ergebnis=ergebnis.isoformat() if ergebnis else None))


def _addiere_monate(d: _dt.date, monate: int) -> tuple[_dt.date, bool]:
    """Ereignisfrist-Variante von § 188 Abs. 2 (ggf. Abs. 3) BGB: der dem
    Ereignistag nach seiner Zahl entsprechende Tag im Zielmonat, sonst
    (Monatsüberlauf) der letzte Tag des Zielmonats. Liefert (Datum,
    ueberlauf)."""
    gesamt = d.year * 12 + (d.month - 1) + monate
    ziel_jahr, ziel_monat0 = divmod(gesamt, 12)
    ziel_monat = ziel_monat0 + 1
    letzter = calendar.monthrange(ziel_jahr, ziel_monat)[1]
    ueberlauf = d.day > letzter
    tag = letzter if ueberlauf else d.day
    return _dt.date(ziel_jahr, ziel_monat, tag), ueberlauf


def _pruefe_bundesland(bundesland: str) -> str:
    land = bundesland.strip().upper()
    if land not in BUNDESLAENDER:
        raise AOEingabeFehler(
            f"unbekanntes Bundesland-Kürzel: {bundesland!r} "
            f"(erlaubt: {', '.join(sorted(BUNDESLAENDER))})")
    return land


# --------------------------------------------------------------------------
# Baustein 1 — Einspruchsfrist
# --------------------------------------------------------------------------

@dataclass
class EinspruchsfristErgebnis:
    bekanntgabe_datum: _dt.date
    fristbeginn: _dt.date
    fristende_rechnerisch: _dt.date
    fristende: _dt.date
    verschoben: bool
    fiktion_verschieben: bool
    aufgabe_zur_post_datum: _dt.date | None
    bundesland: str
    jahresfrist: bool
    rechenkette: list[RechenSchritt] = field(default_factory=list)
    warnungen: list[str] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "bekanntgabe_datum": self.bekanntgabe_datum.isoformat(),
            "aufgabe_zur_post_datum": (self.aufgabe_zur_post_datum.isoformat()
                                       if self.aufgabe_zur_post_datum else None),
            "fiktion_verschieben": self.fiktion_verschieben,
            "bundesland": self.bundesland,
            "jahresfrist": self.jahresfrist,
            "fristbeginn": self.fristbeginn.isoformat(),
            "fristende_rechnerisch": self.fristende_rechnerisch.isoformat(),
            "fristende": self.fristende.isoformat(),
            "verschoben": self.verschoben,
            "rechenkette": [s.as_dict() for s in self.rechenkette],
            "warnungen": list(self.warnungen),
            "hinweise": list(self.hinweise),
            "kalender_termine": [{
                "datum": self.fristende.isoformat(),
                "titel": ("Einspruchsfrist (Jahresfrist § 356 Abs. 2 AO)" if self.jahresfrist
                          else "Einspruchsfrist (§ 355 Abs. 1 AO)"),
                "norm": "§ 356 Abs. 2 AO" if self.jahresfrist else "§ 355 Abs. 1 AO",
            }],
            "quelle": "executor",
        }


def berechne_einspruchsfrist(*, bundesland: str,
                             bekanntgabe_datum: _dt.date | None = None,
                             aufgabe_zur_post_datum: _dt.date | None = None,
                             jahresfrist: bool = False,
                             fiktion_verschieben: bool = False
                             ) -> EinspruchsfristErgebnis:
    if bool(bekanntgabe_datum) == bool(aufgabe_zur_post_datum):
        raise AOEingabeFehler(
            "genau eines von 'bekanntgabe_datum' oder 'aufgabe_zur_post_datum' angeben")
    land = _pruefe_bundesland(bundesland)
    kette: list[RechenSchritt] = []
    warnungen: list[str] = []
    hinweise: list[str] = []

    if aufgabe_zur_post_datum is not None:
        if aufgabe_zur_post_datum < VIERTAGESFIKTION_AB:
            raise AONichtAbgedeckt(
                f"Aufgabe zur Post am {aufgabe_zur_post_datum.isoformat()} liegt vor dem "
                f"{VIERTAGESFIKTION_AB.isoformat()}: die davor geltende Dreitagesfiktion ist "
                "im Quellen-Dossier nur sekundär belegt ([unverifiziert]) und wird nicht "
                "berechnet — Bekanntgabedatum direkt angeben.")
        fiktionsdatum = aufgabe_zur_post_datum + _dt.timedelta(days=FIKTION_TAGE)
        _schritt(kette, "§ 122 Abs. 2 Nr. 1 AO",
                f"Aufgabe zur Post am {aufgabe_zur_post_datum:%d.%m.%Y} "
                f"({_wochentag(aufgabe_zur_post_datum)}): Bekanntgabe gilt am vierten Tage "
                "danach als bewirkt (Zugangsvermutung, gilt seit 01.01.2025).",
                fiktionsdatum)
        if fiktion_verschieben:
            bekanntgabe_datum = _verschiebe_mit_kette(fiktionsdatum, land, kette, warnungen)
            hinweise.append(
                "Option 'fiktion_verschieben=true': der Fiktionstag selbst wurde nach "
                "§ 108 Abs. 3 AO auf den nächsten Werktag verschoben. Diese Übertragung der "
                "BFH-Rechtsprechung zur alten Dreitagesfiktion (BFH v. 14.10.2003, "
                "IX R 68/98, BStBl II 2003, 898) auf die seit 2025 geltende Viertagesfiktion "
                "ist im Quellen-Dossier nicht eigenständig belegt ([unverifiziert]).")
        else:
            bekanntgabe_datum = fiktionsdatum
            hinweise.append(
                "Fiktionstag nicht verschoben (Default 'fiktion_verschieben=false'): die "
                "Übertragung der BFH-Rechtsprechung zur alten Dreitagesfiktion (BFH v. "
                "14.10.2003, IX R 68/98) auf die seit 2025 geltende Viertagesfiktion ist im "
                "Quellen-Dossier nicht eigenständig belegt ([unverifiziert]) — mit "
                "'fiktion_verschieben: true' aktivierbar.")
    else:
        _schritt(kette, "Eingabe", "Bekanntgabedatum direkt angegeben.", bekanntgabe_datum)

    assert bekanntgabe_datum is not None
    fristbeginn = bekanntgabe_datum + _dt.timedelta(days=1)
    _schritt(kette, "§ 108 Abs. 1 AO i. V. m. § 187 Abs. 1 BGB",
            f"Tag der Bekanntgabe ({bekanntgabe_datum:%d.%m.%Y}, "
            f"{_wochentag(bekanntgabe_datum)}) wird nicht mitgerechnet; Fristbeginn am "
            "Folgetag.", fristbeginn)

    norm_frist = "§ 356 Abs. 2 AO" if jahresfrist else "§ 355 Abs. 1 AO"
    monate = 12 if jahresfrist else 1
    ende, ueberlauf = _addiere_monate(bekanntgabe_datum, monate)
    _schritt(kette, f"{norm_frist}, § 108 Abs. 1 AO i. V. m. § 188 Abs. 2 BGB",
            f"{'Jahresfrist' if jahresfrist else 'Monatsfrist'}: Ende mit Ablauf des Tages, "
            "der durch seine Zahl dem Tag der Bekanntgabe entspricht.", ende)
    if ueberlauf:
        _schritt(kette, "§ 188 Abs. 3 BGB",
                f"Der dem Bekanntgabetag ({bekanntgabe_datum.day}.) entsprechende Tag fehlt "
                "im Zielmonat — Ende mit Ablauf des letzten Tages dieses Monats.", ende)

    fristende_rechnerisch = ende
    fristende = _verschiebe_mit_kette(fristende_rechnerisch, land, kette, warnungen)

    return EinspruchsfristErgebnis(
        bekanntgabe_datum=bekanntgabe_datum, fristbeginn=fristbeginn,
        fristende_rechnerisch=fristende_rechnerisch, fristende=fristende,
        verschoben=fristende != fristende_rechnerisch,
        fiktion_verschieben=fiktion_verschieben,
        aufgabe_zur_post_datum=aufgabe_zur_post_datum, bundesland=land,
        jahresfrist=jahresfrist, rechenkette=kette, warnungen=warnungen, hinweise=hinweise)


# --------------------------------------------------------------------------
# Baustein 2 — Abgabefrist
# --------------------------------------------------------------------------

GRUPPEN = ("nicht_beraten", "beraten", "land_forstwirt")


@dataclass
class AbgabefristErgebnis:
    veranlagungszeitraum: int
    gruppe: str
    bundesland: str
    nominal_datum: _dt.date
    fristende: _dt.date
    verschoben: bool
    rechenkette: list[RechenSchritt] = field(default_factory=list)
    warnungen: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "veranlagungszeitraum": self.veranlagungszeitraum,
            "gruppe": self.gruppe,
            "bundesland": self.bundesland,
            "nominal_datum": self.nominal_datum.isoformat(),
            "fristende": self.fristende.isoformat(),
            "verschoben": self.verschoben,
            "rechenkette": [s.as_dict() for s in self.rechenkette],
            "warnungen": list(self.warnungen),
            "kalender_termine": [{
                "datum": self.fristende.isoformat(),
                "titel": f"Abgabefrist VZ {self.veranlagungszeitraum} ({self.gruppe})",
                "norm": "§ 149 Abs. 2/3 AO",
            }],
            "quelle": "executor",
        }


def berechne_abgabefrist(*, veranlagungszeitraum: int, gruppe: str,
                         bundesland: str) -> AbgabefristErgebnis:
    if gruppe not in GRUPPEN:
        raise AOEingabeFehler(f"gruppe muss eine von {GRUPPEN} sein, nicht {gruppe!r}")
    if not isinstance(veranlagungszeitraum, int) or isinstance(veranlagungszeitraum, bool):
        raise AOEingabeFehler("veranlagungszeitraum muss eine ganze Jahreszahl sein")
    if veranlagungszeitraum < 2020:
        raise AONichtAbgedeckt(
            f"Abgabefrist für VZ {veranlagungszeitraum}: das Quellen-Dossier deckt nur VZ ab "
            "2020 ab (Art. 97 § 36 EGAO-Tabelle bzw. Regelfrist ab VZ 2025).")
    land = _pruefe_bundesland(bundesland)
    kette: list[RechenSchritt] = []
    warnungen: list[str] = []

    tabelle = lade_abgabefristen()["veranlagungszeitraeume"]
    eintrag = tabelle.get(str(veranlagungszeitraum))
    if eintrag is not None:
        wert = eintrag.get(gruppe)
        if wert is None:
            raise AONichtAbgedeckt(
                f"'{gruppe}' für VZ {veranlagungszeitraum} ist im Quellen-Dossier nicht "
                "belegt.")
        nominal_datum = _dt.date.fromisoformat(wert)
        _schritt(kette, eintrag["norm"],
                f"EGAO-Sonderfrist VZ {veranlagungszeitraum} ({gruppe}): "
                f"{nominal_datum:%d.%m.%Y}.", nominal_datum)
    else:
        if gruppe == "land_forstwirt":
            raise AONichtAbgedeckt(
                "Abgabefrist für Land-/Forstwirte hängt ab VZ 2025 vom individuellen "
                "Wirtschaftsjahresende ab (§ 149 Abs. 2 Satz 2 AO) — im Quellen-Dossier "
                "nicht als feste Regel belegt, wird nicht berechnet.")
        if gruppe == "nicht_beraten":
            nominal_datum = _dt.date(veranlagungszeitraum + 1, 7, 31)
            _schritt(kette, "§ 149 Abs. 2 Satz 1 AO",
                    "Regelfrist: sieben Monate nach Ablauf des Kalenderjahres.",
                    nominal_datum)
        else:  # beraten
            letzter = calendar.monthrange(veranlagungszeitraum + 2, 2)[1]
            nominal_datum = _dt.date(veranlagungszeitraum + 2, 2, letzter)
            _schritt(kette, "§ 149 Abs. 3 AO",
                    "Regelfrist: letzter Tag des Monats Februar des zweiten folgenden "
                    "Kalenderjahres.", nominal_datum)

    fristende = _verschiebe_mit_kette(nominal_datum, land, kette, warnungen)
    return AbgabefristErgebnis(
        veranlagungszeitraum=veranlagungszeitraum, gruppe=gruppe, bundesland=land,
        nominal_datum=nominal_datum, fristende=fristende,
        verschoben=fristende != nominal_datum, rechenkette=kette, warnungen=warnungen)


# --------------------------------------------------------------------------
# Baustein 3 — Vorauszahlungs-/Anmeldetermine
# --------------------------------------------------------------------------

@dataclass
class VorauszahlungsTermin:
    datum: _dt.date
    nominal_datum: _dt.date
    bezeichnung: str
    schonfrist_ende: _dt.date | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "datum": self.datum.isoformat(),
            "nominal_datum": self.nominal_datum.isoformat(),
            "bezeichnung": self.bezeichnung,
            "schonfrist_ende": self.schonfrist_ende.isoformat() if self.schonfrist_ende else None,
        }


@dataclass
class VorauszahlungsErgebnis:
    jahr: int
    steuerart: str
    bezeichnung: str
    norm: str
    bundesland: str
    rhythmus: str | None
    dauerfristverlaengerung: bool
    termine: list[VorauszahlungsTermin] = field(default_factory=list)
    rechenkette: list[RechenSchritt] = field(default_factory=list)
    warnungen: list[str] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "jahr": self.jahr,
            "steuerart": self.steuerart,
            "bezeichnung": self.bezeichnung,
            "norm": self.norm,
            "bundesland": self.bundesland,
            "rhythmus": self.rhythmus,
            "dauerfristverlaengerung": self.dauerfristverlaengerung,
            "termine": [t.as_dict() for t in self.termine],
            "rechenkette": [s.as_dict() for s in self.rechenkette],
            "warnungen": list(self.warnungen),
            "hinweise": list(self.hinweise),
            "kalender_termine": [{
                "datum": t.datum.isoformat(), "titel": t.bezeichnung, "norm": self.norm,
            } for t in self.termine],
            "quelle": "executor",
        }


def _monatsende(jahr: int, monat: int) -> _dt.date:
    return _dt.date(jahr, monat, calendar.monthrange(jahr, monat)[1])


def _drittletzter_bankarbeitstag(jahr: int, monat: int) -> _dt.date:
    """§ 23 Abs. 1 Satz 2 SGB IV: kein § 108 AO-Verweis (eigenständiger
    Begriff, Dossier Abschnitt 8) — 'Bankarbeitstag' ist hier als Mo-Fr ohne
    bundesweiten gesetzlichen Feiertag verstanden (Interbanken-Clearing ist
    nicht landesspezifisch); diese Auslegung steht nicht wörtlich im Dossier
    (siehe SKILL.md, bewusste Annahme)."""
    # Bundesweite Feiertage hängen nicht vom übergebenen Land ab (feiertage.
    # _bundesweite() ist land-unabhängig) — ein beliebiges gültiges Kürzel reicht.
    d = _monatsende(jahr, monat)
    gezaehlt = 0
    while True:
        if d.weekday() < 5 and not _ist_bundesweiter_feiertag(d):
            gezaehlt += 1
            if gezaehlt == 3:
                return d
        d -= _dt.timedelta(days=1)


def _ist_bundesweiter_feiertag(d: _dt.date) -> bool:
    # Bundesweite Feiertage hängen nicht vom übergebenen Land ab (feiertage.
    # _bundesweite() ist land-unabhängig) — ein beliebiges gültiges Kürzel reicht.
    return any(f.datum == d and f.geltung == "bundesweit" for f in _feiertage_liste(d.year, "BY"))


def berechne_vorauszahlungstermine(*, jahr: int, steuerart: str, bundesland: str,
                                   rhythmus: str | None = None,
                                   dauerfristverlaengerung: bool = False
                                   ) -> VorauszahlungsErgebnis:
    if not isinstance(jahr, int) or isinstance(jahr, bool):
        raise AOEingabeFehler("jahr muss eine ganze Jahreszahl sein")
    katalog = lade_vorauszahlungskatalog()["steuerarten"]
    eintrag = katalog.get(steuerart)
    if eintrag is None:
        raise AOEingabeFehler(
            f"unbekannte steuerart: {steuerart!r} (bekannt: {', '.join(sorted(katalog))})")
    land = _pruefe_bundesland(bundesland)
    kette: list[RechenSchritt] = []
    warnungen: list[str] = []
    hinweise: list[str] = []
    norm = eintrag["norm"]

    if dauerfristverlaengerung and not eintrag.get("dauerfristverlaengerung_moeglich"):
        raise AOEingabeFehler(
            f"'{steuerart}' kennt keine Dauerfristverlängerung (nur 'ustva').")

    nominal_termine: list[tuple[_dt.date, str]] = []

    if eintrag["typ"] == "fixe_termine":
        for monat, tag in eintrag["termine"]:
            nominal_termine.append((
                _dt.date(jahr, monat, tag),
                f"{eintrag['bezeichnung']} {monat:02d}/{jahr}"))
        _schritt(kette, norm,
                f"{eintrag['bezeichnung']}: feste Termine im Jahr {jahr}.", None)

    elif eintrag["typ"] == "periodisch":
        erlaubt = eintrag["erlaubte_rhythmen"]
        if rhythmus is None and len(erlaubt) == 1:
            rhythmus = erlaubt[0]  # einzig möglicher Rhythmus (z. B. 'zm') — kein Pflichtfeld
        if rhythmus not in erlaubt:
            raise AOEingabeFehler(
                f"'{steuerart}' verlangt 'rhythmus' aus {erlaubt}, nicht {rhythmus!r}")
        if rhythmus == "monatlich":
            perioden = [(m, _monatsende(jahr, m)) for m in range(1, 13)]
        elif rhythmus == "quartalsweise":
            perioden = [(q, _monatsende(jahr, q * 3)) for q in range(1, 5)]
        else:  # vierteljaehrlich (lst) — gleiche Quartalsenden, andere Bezeichnung
            if rhythmus == "vierteljaehrlich":
                perioden = [(q, _monatsende(jahr, q * 3)) for q in range(1, 5)]
            else:  # jaehrlich
                perioden = [(1, _monatsende(jahr, 12))]
        frist_tage = eintrag["frist_tage"]
        _schritt(kette, norm,
                f"{eintrag['bezeichnung']}: {frist_tage} Tage nach Ablauf des jeweiligen "
                f"Zeitraums ({rhythmus}).", None)
        for periode, periodenende in perioden:
            faelligkeit = periodenende + _dt.timedelta(days=frist_tage)
            if dauerfristverlaengerung:
                faelligkeit, _ = _addiere_monate(faelligkeit, 1)
            label = f"{eintrag['bezeichnung']} {rhythmus}-Periode {periode}/{jahr}"
            nominal_termine.append((faelligkeit, label))
        if dauerfristverlaengerung:
            _schritt(kette, eintrag["dauerfristverlaengerung_norm"],
                    "Dauerfristverlängerung: Fälligkeit um einen Monat verschoben.", None)

    else:  # drittletzter_bankarbeitstag
        _schritt(kette, norm,
                f"{eintrag['bezeichnung']}: drittletzter Bankarbeitstag jedes Monats im "
                f"Jahr {jahr} — kein Verweis auf § 108 AO (eigenständiger Begriff).", None)
        hinweise.append(
            "'Bankarbeitstag' ist hier als Werktag ohne bundesweiten gesetzlichen "
            "Feiertag verstanden (Interbanken-Clearing bundesweit) — diese Auslegung ist "
            "eine bewusste Annahme, im Quellen-Dossier nicht wörtlich definiert.")
        for monat in range(1, 13):
            d = _drittletzter_bankarbeitstag(jahr, monat)
            nominal_termine.append((d, f"{eintrag['bezeichnung']} {monat:02d}/{jahr}"))

    termine: list[VorauszahlungsTermin] = []
    verschieben = eintrag["typ"] != "drittletzter_bankarbeitstag"
    for nominal_datum, bezeichnung in nominal_termine:
        if verschieben:
            endgueltig = _verschiebe_mit_kette(nominal_datum, land, kette, warnungen)
        else:
            endgueltig = nominal_datum
        schonfrist = endgueltig + _dt.timedelta(days=SCHONFRIST_TAGE)
        termine.append(VorauszahlungsTermin(
            datum=endgueltig, nominal_datum=nominal_datum, bezeichnung=bezeichnung,
            schonfrist_ende=schonfrist))

    if verschieben:
        hinweise.append(
            f"Schonfrist ({SCHONFRIST_TAGE} Tage, § 240 Abs. 3 Satz 1 AO) je Termin als "
            "'schonfrist_ende' ausgewiesen — gilt nicht bei Barzahlung (sofort fällig) oder "
            "Scheckzahlung (§ 240 Abs. 3 Satz 2 i. V. m. § 224 Abs. 2 Nr. 1 AO).")

    return VorauszahlungsErgebnis(
        jahr=jahr, steuerart=steuerart, bezeichnung=eintrag["bezeichnung"], norm=norm,
        bundesland=land, rhythmus=rhythmus, dauerfristverlaengerung=dauerfristverlaengerung,
        termine=termine, rechenkette=kette, warnungen=warnungen, hinweise=hinweise)


# --------------------------------------------------------------------------
# Baustein 4 — Verspätungszuschlag
# --------------------------------------------------------------------------

@dataclass
class VerspaetungszuschlagErgebnis:
    festgesetzte_steuer: Decimal
    anzurechnende_betraege: Decimal
    bemessungsgrundlage: Decimal
    fristende: _dt.date
    abgabedatum: _dt.date
    angefangene_monate: int
    zuschlag_pro_monat: Decimal
    zuschlag_gesamt: Decimal
    hoechstbetrag_erreicht: bool
    rechenkette: list[RechenSchritt] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "festgesetzte_steuer": str(self.festgesetzte_steuer),
            "anzurechnende_betraege": str(self.anzurechnende_betraege),
            "bemessungsgrundlage": str(self.bemessungsgrundlage),
            "fristende": self.fristende.isoformat(),
            "abgabedatum": self.abgabedatum.isoformat(),
            "angefangene_monate": self.angefangene_monate,
            "prozentsatz": str(VERSPAETUNGSZUSCHLAG_PROZENTSATZ),
            "mindestbetrag_je_monat": str(VERSPAETUNGSZUSCHLAG_MINDESTBETRAG),
            "hoechstbetrag": str(VERSPAETUNGSZUSCHLAG_HOECHSTBETRAG),
            "zuschlag_pro_monat": str(self.zuschlag_pro_monat),
            "zuschlag_gesamt": str(self.zuschlag_gesamt),
            "hoechstbetrag_erreicht": self.hoechstbetrag_erreicht,
            "rechenkette": [s.as_dict() for s in self.rechenkette],
            "hinweise": list(self.hinweise),
            "kalender_termine": [{
                "datum": self.fristende.isoformat(),
                "titel": "Fristende (Bezugspunkt Verspätungszuschlag)",
                "norm": "§ 152 Abs. 5 AO",
            }],
            "quelle": "executor",
        }


def _als_decimal(wert: Any, feld: str) -> Decimal:
    if isinstance(wert, bool) or not isinstance(wert, (int, float, str, Decimal)):
        raise AOEingabeFehler(f"'{feld}' muss eine Zahl sein, nicht {wert!r}")
    try:
        return Decimal(str(wert))
    except Exception as exc:  # noqa: BLE001 — Decimal-Parsing, klare Fehlermeldung
        raise AOEingabeFehler(f"'{feld}' ist keine gültige Zahl: {wert!r} ({exc})")


def _addiere_monat_einfach(d: _dt.date) -> _dt.date:
    ergebnis, _ = _addiere_monate(d, 1)
    return ergebnis


def _angefangene_monate(fristende: _dt.date, abgabedatum: _dt.date) -> int:
    if abgabedatum <= fristende:
        return 0
    monate = 0
    cur = fristende
    while cur < abgabedatum:
        cur = _addiere_monat_einfach(cur)
        monate += 1
    return monate


def berechne_verspaetungszuschlag(*, festgesetzte_steuer: Any,
                                  anzurechnende_betraege: Any,
                                  abgabedatum: _dt.date,
                                  fristende: _dt.date) -> VerspaetungszuschlagErgebnis:
    steuer = _als_decimal(festgesetzte_steuer, "festgesetzte_steuer")
    anzurechnen = _als_decimal(anzurechnende_betraege, "anzurechnende_betraege")
    if steuer < 0:
        raise AOEingabeFehler("'festgesetzte_steuer' darf nicht negativ sein")
    if anzurechnen < 0:
        raise AOEingabeFehler("'anzurechnende_betraege' darf nicht negativ sein")

    kette: list[RechenSchritt] = []
    hinweise: list[str] = [
        "Pflicht- vs. Ermessensfall (§ 152 Abs. 1 AO / § 152 Abs. 2 Nr. 1, 2 AO, 14/19 "
        "Monate nach Ablauf des Kalenderjahres, ggf. zeitweilig verlängert durch Art. 97 "
        "§ 36 Abs. 3 Nr. 5 EGAO für VZ 2020-2024) wird hier nur als Normenhinweis "
        "ausgegeben — die Subsumtion ist Kanzleisache, keine Ermessensbewertung durch "
        "diesen Rechner.",
        "§ 152 Abs. 8 Nr. 1 AO: für monatlich oder vierteljährlich abzugebende "
        "Steueranmeldungen (USt-VA, LSt-Anmeldung) gilt Abs. 5 nicht — dieser Rechner ist "
        "nur für Jahressteuererklärungen vorgesehen.",
    ]

    bemessung = steuer - anzurechnen
    if bemessung < 0:
        bemessung = Decimal("0")
    _schritt(kette, "§ 152 Abs. 5 Satz 2 AO",
            f"Bemessungsgrundlage: {steuer} ./. {anzurechnen} (anzurechnende Beträge). "
            "Keine gesetzliche Rundung auf dieser Stufe (§ 152 Abs. 10 AO rundet nur "
            "den Gesamtbetrag).", None)

    monate = _angefangene_monate(fristende, abgabedatum)
    _schritt(kette, "§ 152 Abs. 5 Satz 1 AO",
            f"Verspätung vom {fristende:%d.%m.%Y} (Fristende) bis {abgabedatum:%d.%m.%Y} "
            f"(Abgabedatum): {monate} angefangene(r) Monat(e).", None)

    if monate == 0:
        zuschlag_pro_monat = Decimal("0")
    else:
        prozent_betrag = bemessung * VERSPAETUNGSZUSCHLAG_PROZENTSATZ
        zuschlag_pro_monat = max(prozent_betrag, VERSPAETUNGSZUSCHLAG_MINDESTBETRAG)
    _schritt(kette, "§ 152 Abs. 5 Satz 2 AO",
            f"0,25 % der Bemessungsgrundlage ({bemessung} €) je angefangenem Monat, "
            f"mindestens {VERSPAETUNGSZUSCHLAG_MINDESTBETRAG} € je Monat "
            f"— hier {zuschlag_pro_monat} € je Monat, ungerundet.",
            None)

    zuschlag_summe = zuschlag_pro_monat * monate
    hoechstbetrag_erreicht = zuschlag_summe > VERSPAETUNGSZUSCHLAG_HOECHSTBETRAG
    zuschlag_gedeckelt = min(zuschlag_summe, VERSPAETUNGSZUSCHLAG_HOECHSTBETRAG)
    _schritt(kette, "§ 152 Abs. 10 AO",
            f"Gesamtbetrag {zuschlag_summe} € ({monate} × {zuschlag_pro_monat} €), "
            f"gedeckelt auf höchstens {VERSPAETUNGSZUSCHLAG_HOECHSTBETRAG} €.", None)

    zuschlag_gesamt = zuschlag_gedeckelt.quantize(Decimal("1"), rounding=ROUND_DOWN)
    _schritt(kette, "§ 152 Abs. 10 AO",
            f"Abrundung auf volle Euro: {zuschlag_gedeckelt} € → {zuschlag_gesamt} €.",
            None)

    return VerspaetungszuschlagErgebnis(
        festgesetzte_steuer=steuer, anzurechnende_betraege=anzurechnen,
        bemessungsgrundlage=bemessung, fristende=fristende, abgabedatum=abgabedatum,
        angefangene_monate=monate, zuschlag_pro_monat=zuschlag_pro_monat,
        zuschlag_gesamt=zuschlag_gesamt, hoechstbetrag_erreicht=hoechstbetrag_erreicht,
        rechenkette=kette, hinweise=hinweise)
