#!/usr/bin/env python3
"""stbvv.rechner — StBVV-Gebührenberechnung (Wertgebühr, Zeitgebühr,
Betragsrahmen je Einheit, Auslagenpauschale, USt), P3.

Deckt genau **eine** Hauptberechnung je Anfrage ab (v1, KISS — mehrere
Tätigkeiten in einer Anfrage sind nicht vorgesehen, das ruft Claude als
mehrere Executor-Aufrufe auf):

* **Wertgebühr** (§ 10, § 11 StBVV): Gegenstandswert → Wertstufe der in
  `katalog.json` hinterlegten Tabelle (A-D, `tabellen.json`), volle Gebühr
  × Zehntelsatz im gesetzlichen Rahmen (Untergrenze/Mittelgebühr/Obergrenze/
  gewählter Satz — nie automatisch der Regelfall, § 11 StBVV: Ermessen des
  Steuerberaters).
* **Zeitgebühr** (§ 13 StBVV): Minuten → angefangene Viertelstunden ×
  Satz im Rahmen 16,50-41 Euro. Nur für Stichtage ab 2025-07-01 (aktuelle
  Fassung) — ein früherer Stichtag ist eine Lücke (Exit 2), kein geratener
  Altsatz.
* **Betragsrahmen je Einheit** (§ 34 StBVV, Lohnbuchführung): Anzahl
  Einheiten (Arbeitnehmer[/Abrechnungszeitraum]) × Satz im Rahmen.

Danach optional **Auslagenpauschale** (§ 16 StBVV: 20 %, höchstens 20 Euro)
und **Umsatzsteuer** (§ 15 StBVV, Satz als Eingabe, Default 19 %).

Rundung: der StBVV-Text (§§ 10, 11, 13, 15, 16, 21, 24, 33, 34, 35) enthält
keine eigene Rundungsvorschrift (anders als z. B. § 34 Abs. 2 Satz 2 GKG) —
es wird als Hausregel kaufmännisch auf den Cent gerundet (ROUND_HALF_UP),
in der Rechenkette als solche benannt.

Nur Standardbibliothek. Kein Netzwerkzugriff. Ausschließlich Decimal.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import sys
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path
from typing import Any

_STBVV_DIR = Path(__file__).resolve().parent
_CALC_DIR = _STBVV_DIR.parent
if str(_CALC_DIR) not in sys.path:
    sys.path.insert(0, str(_CALC_DIR))

from rechenschritt import RechenSchritt  # noqa: E402

TABELLEN_PFAD = _STBVV_DIR / "tabellen.json"
KATALOG_PFAD = _STBVV_DIR / "katalog.json"

UST_SATZ_DEFAULT = Decimal("0.19")
AUSLAGENPAUSCHALE_SATZ = Decimal("0.20")   # § 16 StBVV
AUSLAGENPAUSCHALE_MAX = Decimal("20.00")   # § 16 StBVV
ZEITGEBUEHR_MIN = Decimal("16.50")         # § 13 StBVV
ZEITGEBUEHR_MAX = Decimal("41.00")         # § 13 StBVV
ZEITGEBUEHR_AB = _dt.date(2025, 7, 1)      # Stichtag der aktuellen Fassung
VIERTELSTUNDE_MINUTEN = Decimal("15")
REFERENZPUNKTE = ("untergrenze", "mittelgebuehr", "obergrenze")


class StBVVEingabeFehler(ValueError):
    """Ungültige StBVV-Anfrage (Scope, unbekannte Tatbestands-Id, Typfehler, ...)."""


def D(wert: Any) -> Decimal:
    """Wandelt einen Wert strikt in Decimal um — niemals über float (0,1+0,2-
    Falle wäre bei Geldbeträgen ein Haftungsrisiko, CONVENTIONS.md P3)."""
    if isinstance(wert, bool):
        raise StBVVEingabeFehler(f"Zahlenwert erwartet, nicht bool: {wert!r}")
    if isinstance(wert, Decimal):
        return wert
    if isinstance(wert, int):
        return Decimal(wert)
    if isinstance(wert, float):
        raise StBVVEingabeFehler(
            f"Geldbeträge/Sätze müssen als JSON-String (z. B. \"1234.56\") oder "
            f"ganze Zahl übergeben werden, nicht als float: {wert!r}")
    if isinstance(wert, str):
        try:
            d = Decimal(wert.strip())
        except Exception as exc:
            raise StBVVEingabeFehler(f"kein gültiger Dezimalbetrag: {wert!r} ({exc})")
        if not d.is_finite():
            raise StBVVEingabeFehler(f"kein gültiger endlicher Dezimalbetrag: {wert!r}")
        return d
    raise StBVVEingabeFehler(f"Zahlenwert erwartet, nicht {type(wert).__name__}: {wert!r}")


def rundung_cent(betrag: Decimal) -> Decimal:
    """Kaufmännische Rundung auf den vollen Cent — Hausregel, siehe Moduldoc:
    der StBVV-Text schreibt keine Rundung vor."""
    return betrag.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_datum_strikt(wert: Any, feld: str) -> _dt.date:
    if isinstance(wert, bool) or not isinstance(wert, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", wert):
        raise StBVVEingabeFehler(
            f"'{feld}' muss ein ISO-Datum als String im Format JJJJ-MM-TT sein, nicht {wert!r}")
    try:
        return _dt.date.fromisoformat(wert)
    except ValueError as exc:
        raise StBVVEingabeFehler(f"'{feld}' ist kein gültiges ISO-Datum: {wert!r} ({exc})")


def lade_tabellen(pfad: Path | None = None) -> dict[str, Any]:
    return json.loads((pfad or TABELLEN_PFAD).read_text(encoding="utf-8"))


def lade_katalog(pfad: Path | None = None) -> dict[str, dict[str, Any]]:
    rohliste = json.loads((pfad or KATALOG_PFAD).read_text(encoding="utf-8"))
    return {eintrag["id"]: eintrag for eintrag in rohliste}


@dataclass
class VolleGebuehrErgebnis:
    tabelle_id: str
    gegenstandswert: Decimal
    volle_gebuehr: Decimal
    herleitung: str          # Kurztext, was gefunden wurde (Stufe/Fortschreibung)
    tabellen_norm: str       # Fundstelle der Tabelle (Anlage X StBVV)


def volle_gebuehr(tabelle_id: str, gegenstandswert: Decimal,
                  tabellen: dict[str, Any]) -> VolleGebuehrErgebnis:
    """Sucht die volle Gebühr (10/10) für `gegenstandswert` in Tabelle
    `tabelle_id` (A-D, `tabellen.json`): erste Wertstufe mit `bis >= wert`,
    oder — oberhalb der letzten Stufe — die im Text hinterlegte
    Fortschreibungsformel ('je angefangene X Euro'). Fehlt eine
    Fortschreibungsformel für diese Tabelle (Tabelle D Teil a: abweichendes
    Schema, siehe tabellen.json), ist ein Wert oberhalb der letzten Stufe
    eine Lücke (Exit 2) — nie eine geratene Fortschreibung."""
    if tabelle_id not in tabellen:
        raise StBVVEingabeFehler(
            f"unbekannte Tabelle '{tabelle_id}' — bekannt: {', '.join(sorted(tabellen))}")
    tab = tabellen[tabelle_id]
    stufen = tab["stufen"]
    for stufe in stufen:
        bis = D(stufe["bis"])
        if gegenstandswert <= bis:
            return VolleGebuehrErgebnis(
                tabelle_id, gegenstandswert, D(stufe["gebuehr"]),
                f"Wertstufe bis {bis} Euro, {tab['bezeichnung']}", tab["norm"])

    letzte_bis = D(stufen[-1]["bis"])
    fortschreibung = tab.get("fortschreibung")
    if not fortschreibung:
        raise StBVVEingabeFehler(
            f"Gegenstandswert {gegenstandswert} Euro liegt über der höchsten "
            f"Stufe von {tab['bezeichnung']} ({letzte_bis} Euro) — für diese "
            f"Tabelle ist keine Fortschreibungsformel hinterlegt "
            f"({tab.get('fortschreibung_hinweis', 'siehe tabellen.json')})."
            f" Keine automatische Berechnung möglich.")

    gebuehr = D(stufen[-1]["gebuehr"])
    for tier in fortschreibung:
        ab = D(tier["ab"])
        bis = D(tier["bis"]) if tier["bis"] is not None else None
        if gegenstandswert <= ab:
            break
        obergrenze = min(gegenstandswert, bis) if bis is not None else gegenstandswert
        spanne = obergrenze - ab
        schritt = D(tier["je_angefangene_euro"])
        anzahl = int((spanne / schritt).to_integral_value(rounding=ROUND_CEILING))
        gebuehr += anzahl * D(tier["zuschlag"])
        if bis is not None and gegenstandswert <= bis:
            break
    return VolleGebuehrErgebnis(
        tabelle_id, gegenstandswert, rundung_cent(gebuehr),
        f"Fortschreibung über {letzte_bis} Euro hinaus, {tab['bezeichnung']}", tab["norm"])


def _referenzpunkt_satz(satz_min: Decimal, satz_max: Decimal, referenzpunkt: str) -> Decimal:
    if referenzpunkt == "untergrenze":
        return satz_min
    if referenzpunkt == "obergrenze":
        return satz_max
    if referenzpunkt == "mittelgebuehr":
        return (satz_min + satz_max) / 2
    raise StBVVEingabeFehler(
        f"'referenzpunkt' muss einer von {REFERENZPUNKTE} sein, ist {referenzpunkt!r}")


def _waehle_satz(eintrag_min: Decimal, eintrag_max: Decimal, satz: Any,
                 referenzpunkt: Any, feldname: str) -> tuple[Decimal, str]:
    """Wählt den anzuwendenden Satz: entweder ein expliziter Wert (Ermessen
    des Steuerberaters, § 11 StBVV — nie automatisch der Regelfall) oder
    einer der Referenzpunkte 'untergrenze'/'mittelgebuehr'/'obergrenze'.
    Genau eines von beiden, nie beides und nie keines — sonst würde eine
    fehlende Angabe still zur Untergrenze."""
    hat_satz = satz is not None
    hat_referenzpunkt = referenzpunkt is not None
    if hat_satz and hat_referenzpunkt:
        raise StBVVEingabeFehler(
            f"entweder '{feldname}' (expliziter Satz) ODER 'referenzpunkt' "
            f"angeben — nicht beides")
    if not hat_satz and not hat_referenzpunkt:
        raise StBVVEingabeFehler(
            f"'{feldname}' (expliziter Satz im Rahmen) oder 'referenzpunkt' "
            f"({', '.join(REFERENZPUNKTE)}) ist Pflichtangabe — § 11 StBVV "
            f"verlangt eine bewusste Ermessensentscheidung des "
            f"Steuerberaters, keine automatische Annahme.")
    if hat_referenzpunkt:
        if not isinstance(referenzpunkt, str):
            raise StBVVEingabeFehler(f"'referenzpunkt' muss ein String sein, nicht {referenzpunkt!r}")
        gewaehlt = _referenzpunkt_satz(eintrag_min, eintrag_max, referenzpunkt)
        return gewaehlt, f"referenzpunkt='{referenzpunkt}'"
    gewaehlt = D(satz)
    if not (eintrag_min <= gewaehlt <= eintrag_max):
        raise StBVVEingabeFehler(
            f"'{feldname}' {gewaehlt} liegt außerhalb des gesetzlichen Rahmens "
            f"{eintrag_min}-{eintrag_max}")
    return gewaehlt, f"{feldname}={gewaehlt}"


@dataclass
class HauptErgebnis:
    art: str
    bezeichnung: str
    norm: str
    betrag: Decimal
    rechenkette: list[RechenSchritt] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


def berechne_wertgebuehr(tatbestand_id: str, gegenstandswert: Any, *,
                         satz: Any = None, referenzpunkt: Any = None,
                         erstberatung_verbraucher: bool = False) -> HauptErgebnis:
    kat = lade_katalog()
    tab = lade_tabellen()
    if tatbestand_id not in kat:
        raise StBVVEingabeFehler(
            f"unbekannte Tatbestands-Id '{tatbestand_id}' — siehe katalog.json "
            f"für die unterstützten Tätigkeiten (§§ 21, 24, 33, 35 StBVV)")
    eintrag = kat[tatbestand_id]
    if eintrag["art"] != "wertgebuehr":
        raise StBVVEingabeFehler(
            f"Tatbestand '{tatbestand_id}' ist keine Wertgebühr (art="
            f"'{eintrag['art']}') — falscher Anfrage-Block")

    wert_eingabe = D(gegenstandswert)
    if wert_eingabe <= 0:
        raise StBVVEingabeFehler(f"Gegenstandswert muss > 0 sein, ist {wert_eingabe}")

    kette: list[RechenSchritt] = []

    def schritt(norm: str, beschreibung: str, ergebnis: str | None) -> None:
        kette.append(RechenSchritt(schritt=len(kette) + 1, norm=norm,
                                   beschreibung=beschreibung, ergebnis=ergebnis))

    mindestwert = D(eintrag["mindestwert"]) if eintrag.get("mindestwert") else None
    wert = wert_eingabe
    if mindestwert is not None and wert < mindestwert:
        wert = mindestwert
        schritt(eintrag["norm"],
                f"Gegenstandswert {wert_eingabe} Euro liegt unter dem "
                f"gesetzlichen Mindestwert — auf {mindestwert} Euro angehoben "
                f"({eintrag['bemessungsgrundlage']}).", str(wert))

    vg = volle_gebuehr(eintrag["tabelle"], wert, tab)
    schritt(vg.tabellen_norm,
            f"Volle Gebühr (10/10) für Gegenstandswert {wert} Euro: {vg.herleitung}.",
            str(vg.volle_gebuehr))

    satz_min, satz_max = D(eintrag["satz_min"]), D(eintrag["satz_max"])
    gewaehlter_satz, satz_quelle = _waehle_satz(satz_min, satz_max, satz, referenzpunkt, "satz")
    schritt(eintrag["norm"],
            f"Zehntelrahmen {eintrag['darstellung_zehntel']} — gewählter Satz "
            f"{gewaehlter_satz} ({satz_quelle}; Untergrenze {satz_min}, "
            f"Mittelgebühr {(satz_min + satz_max) / 2}, Obergrenze {satz_max}; "
            f"Ermessen des Steuerberaters, § 11 StBVV).", str(gewaehlter_satz))

    betrag = rundung_cent(gewaehlter_satz * vg.volle_gebuehr)
    schritt("Hausregel (kaufmännische Rundung auf den Cent — StBVV-Text ohne eigene Rundungsvorschrift)",
            f"{gewaehlter_satz} x {vg.volle_gebuehr} Euro.", str(betrag))

    if erstberatung_verbraucher:
        kappung = eintrag.get("erstberatung_verbraucher_kappung")
        if not kappung:
            raise StBVVEingabeFehler(
                f"'erstberatung_verbraucher' ist nur für § 21 Abs. 1 StBVV "
                f"(Tatbestand '21-1-rat-auskunft') anwendbar, nicht für "
                f"'{tatbestand_id}'")
        kappungsbetrag = D(kappung)
        if betrag > kappungsbetrag:
            schritt("§ 21 Abs. 1 Satz 2 StBVV",
                    f"Erstberatung eines Verbrauchers: Betrag {betrag} Euro "
                    f"übersteigt die Höchstgrenze {kappungsbetrag} Euro — gekappt.",
                    str(kappungsbetrag))
            betrag = kappungsbetrag

    return HauptErgebnis(
        art="wertgebuehr", bezeichnung=eintrag["bezeichnung"], norm=eintrag["norm"],
        betrag=betrag, rechenkette=kette,
        details={"tatbestand_id": tatbestand_id, "tabelle": eintrag["tabelle"],
                 "gegenstandswert_eingabe": str(wert_eingabe),
                 "gegenstandswert_angewendet": str(wert),
                 "mindestwert_gegriffen": mindestwert is not None and wert_eingabe < mindestwert,
                 "volle_gebuehr": str(vg.volle_gebuehr), "satz": str(gewaehlter_satz)})


def berechne_betragsrahmen(tatbestand_id: str, einheiten: Any, *,
                           satz_je_einheit: Any = None, referenzpunkt: Any = None) -> HauptErgebnis:
    kat = lade_katalog()
    if tatbestand_id not in kat:
        raise StBVVEingabeFehler(f"unbekannte Tatbestands-Id '{tatbestand_id}'")
    eintrag = kat[tatbestand_id]
    if eintrag["art"] != "betragsrahmen_je_einheit":
        raise StBVVEingabeFehler(
            f"Tatbestand '{tatbestand_id}' ist kein Betragsrahmen (art="
            f"'{eintrag['art']}') — falscher Anfrage-Block")
    if not isinstance(einheiten, int) or isinstance(einheiten, bool) or einheiten < 1:
        raise StBVVEingabeFehler(f"'einheiten' muss eine ganze Zahl >= 1 sein, nicht {einheiten!r}")

    kette: list[RechenSchritt] = []

    def schritt(norm: str, beschreibung: str, ergebnis: str | None) -> None:
        kette.append(RechenSchritt(schritt=len(kette) + 1, norm=norm,
                                   beschreibung=beschreibung, ergebnis=ergebnis))

    rmin, rmax = D(eintrag["rahmen_min"]), D(eintrag["rahmen_max"])
    gewaehlter_satz, satz_quelle = _waehle_satz(rmin, rmax, satz_je_einheit, referenzpunkt, "satz_je_einheit")
    schritt(eintrag["norm"],
            f"Betragsrahmen {rmin}-{rmax} Euro {eintrag['einheit']} — "
            f"gewählter Satz {gewaehlter_satz} ({satz_quelle}).", str(gewaehlter_satz))

    betrag = rundung_cent(gewaehlter_satz * einheiten)
    schritt("Hausregel (kaufmännische Rundung auf den Cent)",
            f"{gewaehlter_satz} x {einheiten} {eintrag['einheit']}.", str(betrag))

    return HauptErgebnis(
        art="betragsrahmen_je_einheit", bezeichnung=eintrag["bezeichnung"],
        norm=eintrag["norm"], betrag=betrag, rechenkette=kette,
        details={"tatbestand_id": tatbestand_id, "einheiten": einheiten,
                 "einheit": eintrag["einheit"], "satz_je_einheit": str(gewaehlter_satz)})


def berechne_zeitgebuehr(stichtag: Any, minuten: Any, *,
                         satz: Any = None, referenzpunkt: Any = None) -> HauptErgebnis:
    tag = stichtag if isinstance(stichtag, _dt.date) else parse_datum_strikt(stichtag, "stichtag")
    if tag < ZEITGEBUEHR_AB:
        raise StBVVEingabeFehler(
            f"Zeitgebühr § 13 StBVV: Stichtag {tag.isoformat()} liegt vor "
            f"{ZEITGEBUEHR_AB.isoformat()} (aktuelle Fassung, BGBl. 2025 I "
            f"Nr. 105) — für frühere Stichtage ist kein Satz primärquellig "
            f"geprüft, keine automatische Berechnung möglich.")
    if not isinstance(minuten, int) or isinstance(minuten, bool) or minuten < 1:
        raise StBVVEingabeFehler(f"'minuten' muss eine ganze Zahl >= 1 sein, nicht {minuten!r}")

    kette: list[RechenSchritt] = []

    def schritt(norm: str, beschreibung: str, ergebnis: str | None) -> None:
        kette.append(RechenSchritt(schritt=len(kette) + 1, norm=norm,
                                   beschreibung=beschreibung, ergebnis=ergebnis))

    einheiten = int((Decimal(minuten) / VIERTELSTUNDE_MINUTEN).to_integral_value(rounding=ROUND_CEILING))
    schritt("§ 13 StBVV",
            f"{minuten} Minuten -> {einheiten} angefangene Viertelstunde(n).",
            str(einheiten))

    gewaehlter_satz, satz_quelle = _waehle_satz(
        ZEITGEBUEHR_MIN, ZEITGEBUEHR_MAX, satz, referenzpunkt, "satz")
    schritt("§ 13 StBVV",
            f"Rahmen {ZEITGEBUEHR_MIN}-{ZEITGEBUEHR_MAX} Euro je angefangene "
            f"Viertelstunde — gewählter Satz {gewaehlter_satz} ({satz_quelle}).",
            str(gewaehlter_satz))

    betrag = rundung_cent(gewaehlter_satz * einheiten)
    schritt("Hausregel (kaufmännische Rundung auf den Cent)",
            f"{gewaehlter_satz} x {einheiten} Einheit(en).", str(betrag))

    return HauptErgebnis(
        art="zeitgebuehr", bezeichnung="Zeitgebühr", norm="§ 13 StBVV", betrag=betrag,
        rechenkette=kette,
        details={"stichtag": tag.isoformat(), "minuten": minuten, "einheiten": einheiten,
                 "satz_je_viertelstunde": str(gewaehlter_satz)})


def berechne_auslagenpauschale(gebuehren_summe: Decimal) -> tuple[Decimal, RechenSchritt]:
    roh = rundung_cent(gebuehren_summe * AUSLAGENPAUSCHALE_SATZ)
    pauschale = min(roh, AUSLAGENPAUSCHALE_MAX)
    schritt = RechenSchritt(
        schritt=0, norm="§ 16 StBVV",
        beschreibung=(f"Auslagenpauschale — 20 % von {gebuehren_summe} Euro = "
                     f"{roh} Euro, gedeckelt auf höchstens {AUSLAGENPAUSCHALE_MAX} "
                     f"Euro (in derselben Angelegenheit)."),
        ergebnis=str(pauschale))
    return pauschale, schritt


def berechne_ust(netto: Decimal, satz: Decimal) -> tuple[Decimal, RechenSchritt]:
    ust = rundung_cent(netto * satz)
    schritt = RechenSchritt(
        schritt=0, norm="§ 15 StBVV",
        beschreibung=f"Umsatzsteuer — {satz * 100} % von {netto} Euro.",
        ergebnis=str(ust))
    return ust, schritt
