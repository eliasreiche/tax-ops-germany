#!/usr/bin/env python3
"""stbvv/executor — CLI-Executor (P2/P3): JSON-Eingabe rein, JSON-Report raus.

Wird vom Skill `stbvv-rechner` aufgerufen. Das Modell (Claude) rechnet nie
selbst — es übergibt die Eingabedatei, liest den Report und stellt ihn dar.
Jeder Geldbetrag im Report stammt aus diesem Executor (Deterministik-Grenze,
CONVENTIONS.md P3).

Genau **ein** Hauptberechnungs-Block je Anfrage (v1, KISS):

  * "wertgebuehr": {"tatbestand_id", "gegenstandswert",
                    "satz" ODER "referenzpunkt", optional "erstberatung_verbraucher"}
  * "zeitgebuehr": {"stichtag", "minuten", "satz" ODER "referenzpunkt"}
  * "betragsrahmen": {"tatbestand_id", "einheiten",
                      "satz_je_einheit" ODER "referenzpunkt"}

`referenzpunkt` ist einer von "untergrenze"/"mittelgebuehr"/"obergrenze" —
Alternative zu einem expliziten Satz, nie beides zugleich, nie stillschweigend
weder-noch (§ 11 StBVV: Ermessen des Steuerberaters).

Danach optional, beide Default `true`:

  * "auslagenpauschale": bool (§ 16 StBVV, 20 %, höchstens 20 Euro)
  * "umsatzsteuer": bool, dazu "umsatzsteuersatz" (Default "0.19", § 15 StBVV)

Beispiel:

    {
      "wertgebuehr": {
        "tatbestand_id": "24-1-nr1-est-erklaerung",
        "gegenstandswert": "50000.00",
        "referenzpunkt": "mittelgebuehr"
      },
      "auslagenpauschale": true,
      "umsatzsteuer": true
    }

CLI:
    python3 core/calc/stbvv/executor.py --input ANFRAGE.json [--output REPORT.json]

Exit-Codes: 0 = Report erzeugt, 2 = Eingabefehler.
"""
from __future__ import annotations

import functools
import sys
from pathlib import Path
from typing import Any

_STBVV_DIR = Path(__file__).resolve().parent
_CALC_DIR = _STBVV_DIR.parent
if str(_CALC_DIR) not in sys.path:
    sys.path.insert(0, str(_CALC_DIR))

from cli import (  # noqa: E402
    CliFehler,
    lese_json_objekt,
    pflichtfeld,
    schreibe_report,
    standard_parser,
)
from stbvv.rechner import (  # noqa: E402
    StBVVEingabeFehler,
    UST_SATZ_DEFAULT,
    D,
    berechne_auslagenpauschale,
    berechne_betragsrahmen,
    berechne_ust,
    berechne_wertgebuehr,
    berechne_zeitgebuehr,
    rundung_cent,
)

_pflichtfeld = functools.partial(pflichtfeld, fehler=StBVVEingabeFehler)

_TOP_FELDER = ("wertgebuehr", "zeitgebuehr", "betragsrahmen",
              "auslagenpauschale", "umsatzsteuer", "umsatzsteuersatz")
_WERTGEBUEHR_FELDER = ("tatbestand_id", "gegenstandswert", "satz", "referenzpunkt",
                       "erstberatung_verbraucher")
_ZEITGEBUEHR_FELDER = ("stichtag", "minuten", "satz", "referenzpunkt")
_BETRAGSRAHMEN_FELDER = ("tatbestand_id", "einheiten", "satz_je_einheit", "referenzpunkt")


def _nur_erlaubte_felder(block: dict[str, Any], erlaubt: tuple[str, ...], kontext: str) -> None:
    for feld in block:
        if feld not in erlaubt:
            raise StBVVEingabeFehler(
                f"unbekanntes Feld {kontext}: '{feld}' (erlaubt: "
                f"{', '.join(repr(f) for f in erlaubt)})")


def _pruefe_bool(wert: Any, feld: str) -> bool:
    if not isinstance(wert, bool):
        raise StBVVEingabeFehler(f"'{feld}' muss ein JSON-Boolean sein, nicht {wert!r}")
    return wert


def baue_report(eingabe: dict[str, Any], quelle_datei: str) -> dict[str, Any]:
    _nur_erlaubte_felder(eingabe, _TOP_FELDER, "auf oberster Ebene")

    bloecke_vorhanden = [b for b in ("wertgebuehr", "zeitgebuehr", "betragsrahmen")
                        if eingabe.get(b) is not None]
    if len(bloecke_vorhanden) != 1:
        raise StBVVEingabeFehler(
            f"Anfrage muss genau EINEN Hauptberechnungs-Block enthalten "
            f"('wertgebuehr', 'zeitgebuehr' oder 'betragsrahmen') — gefunden: "
            f"{bloecke_vorhanden or 'keinen'}")

    if "wertgebuehr" in bloecke_vorhanden:
        block = eingabe["wertgebuehr"]
        if not isinstance(block, dict):
            raise StBVVEingabeFehler("'wertgebuehr' muss ein JSON-Objekt sein")
        _nur_erlaubte_felder(block, _WERTGEBUEHR_FELDER, "im Block 'wertgebuehr'")
        ergebnis = berechne_wertgebuehr(
            _pflichtfeld(block, "tatbestand_id"),
            _pflichtfeld(block, "gegenstandswert"),
            satz=block.get("satz"), referenzpunkt=block.get("referenzpunkt"),
            erstberatung_verbraucher=_pruefe_bool(
                block.get("erstberatung_verbraucher", False), "erstberatung_verbraucher"))
    elif "zeitgebuehr" in bloecke_vorhanden:
        block = eingabe["zeitgebuehr"]
        if not isinstance(block, dict):
            raise StBVVEingabeFehler("'zeitgebuehr' muss ein JSON-Objekt sein")
        _nur_erlaubte_felder(block, _ZEITGEBUEHR_FELDER, "im Block 'zeitgebuehr'")
        ergebnis = berechne_zeitgebuehr(
            _pflichtfeld(block, "stichtag"), _pflichtfeld(block, "minuten"),
            satz=block.get("satz"), referenzpunkt=block.get("referenzpunkt"))
    else:
        block = eingabe["betragsrahmen"]
        if not isinstance(block, dict):
            raise StBVVEingabeFehler("'betragsrahmen' muss ein JSON-Objekt sein")
        _nur_erlaubte_felder(block, _BETRAGSRAHMEN_FELDER, "im Block 'betragsrahmen'")
        ergebnis = berechne_betragsrahmen(
            _pflichtfeld(block, "tatbestand_id"), _pflichtfeld(block, "einheiten"),
            satz_je_einheit=block.get("satz_je_einheit"), referenzpunkt=block.get("referenzpunkt"))

    kette = list(ergebnis.rechenkette)

    zwischensumme = ergebnis.betrag
    auslagen_an = _pruefe_bool(eingabe.get("auslagenpauschale", True), "auslagenpauschale")
    pauschale = D("0.00")
    if auslagen_an:
        pauschale, schritt = berechne_auslagenpauschale(zwischensumme)
        schritt.schritt = len(kette) + 1
        kette.append(schritt)

    netto = rundung_cent(zwischensumme + pauschale)
    kette.append(type(kette[0])(
        schritt=len(kette) + 1, norm="Netto",
        beschreibung="Gebühr zzgl. Auslagenpauschale (sofern angefordert).",
        ergebnis=str(netto)))

    ust_an = _pruefe_bool(eingabe.get("umsatzsteuer", True), "umsatzsteuer")
    ust_satz = D(eingabe.get("umsatzsteuersatz", str(UST_SATZ_DEFAULT))) if ust_an else D("0")
    ust = D("0.00")
    if ust_an:
        ust, schritt = berechne_ust(netto, ust_satz)
        schritt.schritt = len(kette) + 1
        kette.append(schritt)

    brutto = rundung_cent(netto + ust)

    return {
        "meta": {
            "erzeugt_von": "core/calc/stbvv/executor.py",
            "quelle_datei": quelle_datei,
            "deterministik": ("Alle Geldbeträge in diesem Report sind "
                              "Executor-Ergebnisse (P3), nicht modellgeneriert."),
        },
        "berechnung": {
            "art": ergebnis.art, "bezeichnung": ergebnis.bezeichnung,
            "norm": ergebnis.norm, "details": ergebnis.details,
        },
        "rechenkette": [s.as_dict() for s in kette],
        "ergebnis": {
            "gebuehr": str(zwischensumme),
            "auslagenpauschale": str(pauschale) if auslagen_an else None,
            "netto": str(netto),
            "umsatzsteuersatz": str(ust_satz) if ust_an else None,
            "umsatzsteuer": str(ust) if ust_an else None,
            "brutto": str(brutto),
            "quelle": "executor",
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = standard_parser(__doc__, "JSON-Eingabedatei (StBVV-Anfrage)").parse_args(argv)

    input_pfad = Path(args.input)
    try:
        eingabe = lese_json_objekt(input_pfad)
        report = baue_report(eingabe, quelle_datei=str(input_pfad))
        schreibe_report(report, args.output)
    except (CliFehler, StBVVEingabeFehler, ValueError, ArithmeticError) as exc:
        # ValueError/ArithmeticError als Sicherheitsnetz (u. a.
        # decimal.InvalidOperation), damit nie ein Traceback statt Exit 2 erscheint.
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
