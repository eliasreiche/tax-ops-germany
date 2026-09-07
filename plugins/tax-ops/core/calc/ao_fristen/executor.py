#!/usr/bin/env python3
"""ao_fristen — CLI-Executor (P2/P3): JSON-Eingabe rein, JSON-Report raus.

Wird vom Skill `ao-fristenrechner` aufgerufen. Das Modell (Claude) rechnet
nie selbst — es übergibt die Eingabedatei, liest den Report und stellt ihn
dar. Jeder Datums-/Geldwert im Report stammt aus diesem Executor
(Deterministik-Grenze, CONVENTIONS.md P3).

Eingabe (JSON-Datei, Pflichtfeld `modus`, Schema siehe plugins/tax-ops/
skills/ao-fristenrechner/schema/README.md):

    {"modus": "einspruch", "bundesland": "NW",
     "bekanntgabe_datum": "2026-01-15"}                     // ODER aufgabe_zur_post_datum

    {"modus": "abgabefrist", "veranlagungszeitraum": 2024,
     "gruppe": "beraten", "bundesland": "NW"}

    {"modus": "vorauszahlung", "jahr": 2026, "steuerart": "ustva",
     "bundesland": "NW", "rhythmus": "monatlich"}

    {"modus": "verspaetungszuschlag", "festgesetzte_steuer": 10000,
     "anzurechnende_betraege": 2000, "abgabedatum": "2026-10-15",
     "fristende": "2026-07-31"}

CLI:
    python3 core/calc/ao_fristen/executor.py --input ANFRAGE.json [--output REPORT.json]

Exit-Codes: 0 = Report erzeugt, 1 = Eingabefehler, 2 = im Quellen-Dossier
nicht belegte Regel (nicht abgedeckt) — siehe rechner.py Modul-Docstring.
"""
from __future__ import annotations

import datetime as _dt
import functools
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cli import (  # noqa: E402
    CliFehler,
    lese_json_objekt,
    pflichtfeld,
    schreibe_report,
    standard_parser,
)
from ao_fristen.rechner import (  # noqa: E402
    AOEingabeFehler,
    AONichtAbgedeckt,
    berechne_abgabefrist,
    berechne_einspruchsfrist,
    berechne_verspaetungszuschlag,
    berechne_vorauszahlungstermine,
)

MODI = ("einspruch", "abgabefrist", "vorauszahlung", "verspaetungszuschlag")

_pflichtfeld = functools.partial(pflichtfeld, fehler=AOEingabeFehler)
_DATUM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _datum(wert: Any, feld: str) -> _dt.date:
    # Strikt JJJJ-MM-TT (Datei-Kontrakt): fromisoformat() allein würde über
    # den str()-Umweg auch JSON-Zahlen oder die Wochen-Notation schlucken.
    if not isinstance(wert, str) or not _DATUM_RE.match(wert):
        raise AOEingabeFehler(
            f"'{feld}' muss ein ISO-Datum als String im Format JJJJ-MM-TT sein, "
            f"nicht {wert!r}")
    try:
        return _dt.date.fromisoformat(wert)
    except ValueError as exc:
        raise AOEingabeFehler(f"'{feld}' ist kein gültiges ISO-Datum: {wert!r} ({exc})")


def _optional_datum(eingabe: dict[str, Any], feld: str) -> _dt.date | None:
    wert = eingabe.get(feld)
    return _datum(wert, feld) if wert is not None else None


def _bool_feld(eingabe: dict[str, Any], feld: str, default: bool) -> bool:
    wert = eingabe.get(feld, default)
    if not isinstance(wert, bool):
        # Strenge Typprüfung: der JSON-String "false" wäre truthy — bei einem
        # Haftungs-Tool eine stille Fehlinterpretation.
        raise AOEingabeFehler(f"'{feld}' muss ein JSON-Boolean (true/false) sein, nicht {wert!r}")
    return wert


def _ganzzahl(wert: Any, feld: str) -> int:
    if not isinstance(wert, int) or isinstance(wert, bool):
        raise AOEingabeFehler(f"'{feld}' muss eine ganze Zahl sein, nicht {wert!r}")
    return wert


def _baue_einspruch(eingabe: dict[str, Any]) -> dict[str, Any]:
    bundesland = str(_pflichtfeld(eingabe, "bundesland"))
    bekanntgabe = _optional_datum(eingabe, "bekanntgabe_datum")
    aufgabe = _optional_datum(eingabe, "aufgabe_zur_post_datum")
    jahresfrist = _bool_feld(eingabe, "jahresfrist", False)
    fiktion_verschieben = _bool_feld(eingabe, "fiktion_verschieben", False)
    ergebnis = berechne_einspruchsfrist(
        bundesland=bundesland, bekanntgabe_datum=bekanntgabe,
        aufgabe_zur_post_datum=aufgabe, jahresfrist=jahresfrist,
        fiktion_verschieben=fiktion_verschieben)
    return ergebnis.as_dict()


def _baue_abgabefrist(eingabe: dict[str, Any]) -> dict[str, Any]:
    vz = _ganzzahl(_pflichtfeld(eingabe, "veranlagungszeitraum"), "veranlagungszeitraum")
    gruppe = str(_pflichtfeld(eingabe, "gruppe"))
    bundesland = str(_pflichtfeld(eingabe, "bundesland"))
    ergebnis = berechne_abgabefrist(
        veranlagungszeitraum=vz, gruppe=gruppe, bundesland=bundesland)
    return ergebnis.as_dict()


def _baue_vorauszahlung(eingabe: dict[str, Any]) -> dict[str, Any]:
    jahr = _ganzzahl(_pflichtfeld(eingabe, "jahr"), "jahr")
    steuerart = str(_pflichtfeld(eingabe, "steuerart"))
    bundesland = str(_pflichtfeld(eingabe, "bundesland"))
    rhythmus = eingabe.get("rhythmus")
    dauerfristverlaengerung = _bool_feld(eingabe, "dauerfristverlaengerung", False)
    ergebnis = berechne_vorauszahlungstermine(
        jahr=jahr, steuerart=steuerart, bundesland=bundesland,
        rhythmus=str(rhythmus) if rhythmus is not None else None,
        dauerfristverlaengerung=dauerfristverlaengerung)
    return ergebnis.as_dict()


def _baue_verspaetungszuschlag(eingabe: dict[str, Any]) -> dict[str, Any]:
    steuer = _pflichtfeld(eingabe, "festgesetzte_steuer")
    anzurechnen = eingabe.get("anzurechnende_betraege", 0)
    abgabedatum = _datum(_pflichtfeld(eingabe, "abgabedatum"), "abgabedatum")
    fristende = _datum(_pflichtfeld(eingabe, "fristende"), "fristende")
    ergebnis = berechne_verspaetungszuschlag(
        festgesetzte_steuer=steuer, anzurechnende_betraege=anzurechnen,
        abgabedatum=abgabedatum, fristende=fristende)
    return ergebnis.as_dict()


_BAUER = {
    "einspruch": _baue_einspruch,
    "abgabefrist": _baue_abgabefrist,
    "vorauszahlung": _baue_vorauszahlung,
    "verspaetungszuschlag": _baue_verspaetungszuschlag,
}


def baue_report(eingabe: dict[str, Any], quelle_datei: str) -> dict[str, Any]:
    modus = str(_pflichtfeld(eingabe, "modus"))
    if modus not in MODI:
        raise AOEingabeFehler(f"'modus' muss eine von {MODI} sein, nicht {modus!r}")
    ergebnis = _BAUER[modus](eingabe)
    return {
        "meta": {
            "erzeugt_von": "core/calc/ao_fristen/executor.py",
            "modus": modus,
            "quelle_datei": quelle_datei,
            "deterministik": ("Alle Datums-/Zahlenwerte in diesem Report sind "
                              "Executor-Ergebnisse (P3), nicht modellgeneriert."),
        },
        "modus": modus,
        **ergebnis,
    }


def main(argv: list[str] | None = None) -> int:
    args = standard_parser(__doc__, "JSON-Eingabedatei (AO-Fristanfrage)").parse_args(argv)
    input_pfad = Path(args.input)
    try:
        eingabe = lese_json_objekt(input_pfad)
    except CliFehler as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    try:
        report = baue_report(eingabe, quelle_datei=str(input_pfad))
    except AONichtAbgedeckt as exc:
        print(f"Nicht abgedeckt: {exc}", file=sys.stderr)
        return 2
    except (AOEingabeFehler, ValueError, OverflowError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    try:
        schreibe_report(report, args.output)
    except CliFehler as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
