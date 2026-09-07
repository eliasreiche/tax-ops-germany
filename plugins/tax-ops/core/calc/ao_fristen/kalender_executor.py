#!/usr/bin/env python3
"""ao_fristen/kalender — CLI-Executor (P2/P3): AO-Fristen-Report rein,
Kalender raus.

Zweiter Executor des Skills `ao-fristenrechner`. Nimmt **ausschließlich**
einen JSON-Report von `executor.py` (jeder der vier Modi: einspruch,
abgabefrist, vorauszahlung, verspaetungszuschlag) und erzeugt daraus einen
Kalender-/Docketing-Export (iCal `.ics` oder CSV) — ein VEVENT/eine CSV-Zeile
je Eintrag in `report["kalender_termine"]` (jeder Modus liefert diese Liste
normiert, ein bis zwölf Einträge).

Deterministik-Grenze (P3): Jeder Datumswert im Export stammt unverändert aus
dem Report. Das Modell rechnet nie selbst.

„Re-Export nur bei Korrektur" (Datei-Ebene, wie legal-ops-germany
core/calc/fristen/kalender_executor.py): Die VEVENT-`UID` ist ein
deterministischer Hash aus Modus, Eingabe-Echo des Reports und dem
Termin-Datum. Unveränderte Frist → identische Bytes → Re-Import
aktualisiert dasselbe Ereignis (kein Duplikat); eine korrigierte Eingabe
ändert die Identität → neue UID → neues Ereignis.

CLI:
    python3 core/calc/ao_fristen/kalender_executor.py \
      --report REPORT.json [--format ics|csv|beide] \
      [--output DATEI | --output-dir ORDNER] \
      [--aktenzeichen AZ] [--vorlauftage N]

Exit-Codes: 0 = Export erzeugt, 1 = Eingabefehler (kein Traceback).
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any

PRODID = "-//tax-ops-germany//ao-fristenrechner//DE"
UID_DOMAIN = "ao-fristenrechner.tax-ops"
ZWEITKONTROLLE = ("Zweitkontrolle bleibt zwingend: Dieser Export ersetzt keinen "
                  "Fristenkalender mit Vier-Augen-Prinzip der Kanzlei. Import und "
                  "Kontrolle im Zielsystem verantwortet die Kanzlei.")


class ExportEingabeFehler(ValueError):
    """Eingabefehler → Exit 1 mit klarer Meldung, nie Traceback."""


# --------------------------------------------------------------------------
# Report lesen & prüfen
# --------------------------------------------------------------------------

def _lade_report(pfad: Path) -> dict[str, Any]:
    if not pfad.is_file():
        raise ExportEingabeFehler(f"Report-Datei nicht gefunden: {pfad}")
    try:
        report = json.loads(pfad.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExportEingabeFehler(f"Report-Datei ist kein gültiges JSON: {exc}")
    if not isinstance(report, dict):
        raise ExportEingabeFehler("Report muss ein JSON-Objekt sein")
    if report.get("quelle") != "executor":
        # Schutz gegen modellgenerierte Fantasie-Reports (P3): nur echte
        # Executor-Reports exportieren.
        raise ExportEingabeFehler(
            "Report ist nicht als Executor-Ergebnis markiert ('quelle' != "
            "'executor') — es werden nur Reports aus core/calc/ao_fristen/executor.py "
            "exportiert, keine modellgenerierten Werte (P3)")
    termine = report.get("kalender_termine")
    if not isinstance(termine, list) or not termine:
        raise ExportEingabeFehler(
            "kein gültiger AO-Fristen-Report: 'kalender_termine' fehlt oder ist leer — "
            "erwartet wird die Ausgabe von core/calc/ao_fristen/executor.py")
    return report


def _datum(iso: str, feld: str) -> _dt.date:
    try:
        return _dt.date.fromisoformat(iso)
    except (ValueError, TypeError):
        raise ExportEingabeFehler(f"'{feld}' ist kein ISO-Datum: {iso!r}")


def vorlauftage_arg(wert: str) -> int:
    """argparse-`type`: ganze Zahl >= 0."""
    try:
        n = int(wert)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"'vorlauftage' muss eine ganze Zahl >= 0 sein: {wert!r}")
    if n < 0:
        raise argparse.ArgumentTypeError(f"'vorlauftage' darf nicht negativ sein: {n}")
    return n


# --------------------------------------------------------------------------
# UID (Idempotenz)
# --------------------------------------------------------------------------

def _identitaet(report: dict[str, Any], termin: dict[str, Any],
               aktenzeichen: str | None) -> str:
    """Stabile, korrektur-empfindliche Identität eines Kalender-Termins:
    Modus + normierte Eingabe-Werte des Reports + der Termin selbst."""
    teile = [str(report.get("modus"))]
    for feld in sorted(k for k in report if k not in
                       ("meta", "rechenkette", "warnungen", "hinweise",
                        "kalender_termine", "quelle", "termine")):
        teile.append(f"{feld}={report[feld]}")
    teile.append(f"datum={termin.get('datum')}")
    teile.append(f"titel={termin.get('titel')}")
    teile.append(f"az={(aktenzeichen or '').strip()}")
    roh = "|".join(teile)
    return hashlib.sha1(roh.encode("utf-8")).hexdigest()[:16]


def _uid(report: dict[str, Any], termin: dict[str, Any], aktenzeichen: str | None) -> str:
    return f"{_identitaet(report, termin, aktenzeichen)}@{UID_DOMAIN}"


# --------------------------------------------------------------------------
# Gemeinsame Feldaufbereitung
# --------------------------------------------------------------------------

def _beschreibungszeilen(report: dict[str, Any], termin: dict[str, Any],
                         vorfrist: _dt.date, vorlauftage: int) -> list[str]:
    z: list[str] = []
    norm = termin.get("norm")
    if norm:
        z.append(f"Norm: {norm} ✅ (verifiziert: aus Executor-Report)")
    z.append(f"Termin: {_datum(termin['datum'], 'termin.datum').strftime('%d.%m.%Y')}")
    z.append(f"Vorfrist ({vorlauftage} Tage vorher): {vorfrist.strftime('%d.%m.%Y')}")
    for w in report.get("warnungen", []):
        z.append(f"Warnung: {w}")
    for h in report.get("hinweise", []):
        z.append(f"Hinweis: {h}")
    z.append(ZWEITKONTROLLE)
    return z


# --------------------------------------------------------------------------
# iCal (RFC 5545)
# --------------------------------------------------------------------------

def _ical_escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def _fold(zeile: str) -> str:
    """Content-Line-Folding auf <= 75 Oktetts (RFC 5545 §3.1)."""
    roh = zeile.encode("utf-8")
    if len(roh) <= 75:
        return zeile
    teile: list[bytes] = []
    rest = roh
    grenze = 75
    while len(rest) > grenze:
        schnitt = grenze
        while schnitt > 0 and (rest[schnitt] & 0xC0) == 0x80:
            schnitt -= 1
        teile.append(rest[:schnitt])
        rest = rest[schnitt:]
        grenze = 74
    teile.append(rest)
    return "\r\n ".join(t.decode("utf-8") for t in teile)


def _dt_compact(datum: _dt.date) -> str:
    return datum.strftime("%Y%m%d")


def _vevent(report: dict[str, Any], termin: dict[str, Any], *, aktenzeichen: str | None,
           vorlauftage: int) -> list[str]:
    datum = _datum(termin["datum"], "termin.datum")
    vorfrist = datum - _dt.timedelta(days=vorlauftage)
    uid = _uid(report, termin, aktenzeichen)
    dtstamp = f"{_dt_compact(datum)}T000000Z"
    dtstart = _dt_compact(datum)
    dtend = _dt_compact(datum + _dt.timedelta(days=1))
    titel = termin.get("titel") or "AO-Frist"
    if aktenzeichen:
        titel += f" — Az. {aktenzeichen.strip()}"
    beschreibung = _ical_escape("\n".join(
        _beschreibungszeilen(report, termin, vorfrist, vorlauftage)))
    return [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;VALUE=DATE:{dtstart}",
        f"DTEND;VALUE=DATE:{dtend}",
        f"SUMMARY:{_ical_escape(titel)}",
        f"DESCRIPTION:{beschreibung}",
        "SEQUENCE:0",
        "STATUS:CONFIRMED",
        "TRANSP:TRANSPARENT",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_ical_escape('Vorfrist: ' + titel)}",
        f"TRIGGER:-P{vorlauftage}D",
        "END:VALARM",
        "END:VEVENT",
    ]


def baue_ical(report: dict[str, Any], *, aktenzeichen: str | None,
             vorlauftage: int) -> str:
    zeilen = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for termin in report["kalender_termine"]:
        zeilen.extend(_vevent(report, termin, aktenzeichen=aktenzeichen,
                              vorlauftage=vorlauftage))
    zeilen.append("END:VCALENDAR")
    return "\r\n".join(_fold(z) for z in zeilen) + "\r\n"


# --------------------------------------------------------------------------
# CSV (semikolon-getrennt, DE-Kanzleisoftware-freundlich)
# --------------------------------------------------------------------------

CSV_SPALTEN = ["datum", "vorfrist", "vorlauftage", "titel", "norm", "modus",
              "aktenzeichen", "uid", "quelle"]


def baue_csv(report: dict[str, Any], *, aktenzeichen: str | None,
            vorlauftage: int) -> str:
    puffer = io.StringIO()
    schreiber = csv.writer(puffer, delimiter=";", lineterminator="\r\n")
    schreiber.writerow(CSV_SPALTEN)
    for termin in report["kalender_termine"]:
        datum = _datum(termin["datum"], "termin.datum")
        vorfrist = datum - _dt.timedelta(days=vorlauftage)
        zeile = {
            "datum": datum.isoformat(),
            "vorfrist": vorfrist.isoformat(),
            "vorlauftage": vorlauftage,
            "titel": termin.get("titel") or "AO-Frist",
            "norm": termin.get("norm") or "",
            "modus": report.get("modus"),
            "aktenzeichen": (aktenzeichen or "").strip(),
            "uid": _uid(report, termin, aktenzeichen),
            "quelle": "executor",
        }
        schreiber.writerow([zeile[s] for s in CSV_SPALTEN])
    return puffer.getvalue()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _schreibe(pfad: Path, inhalt: str) -> None:
    try:
        pfad.write_text(inhalt, encoding="utf-8", newline="")
    except OSError as exc:
        raise ExportEingabeFehler(f"Datei kann nicht geschrieben werden: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", required=True,
                        help="JSON-Report aus core/calc/ao_fristen/executor.py")
    parser.add_argument("--format", choices=["ics", "csv", "beide"], default="ics",
                        help="Exportformat (Default: ics)")
    parser.add_argument("--output", help="Zieldatei (nur für ein Format)")
    parser.add_argument("--output-dir",
                        help="Zielordner für --format beide (Dateiname aus UID der ersten Zeile)")
    parser.add_argument("--aktenzeichen", help="Aktenzeichen/Mandant (Label, kein Rechenwert)")
    parser.add_argument("--vorlauftage", type=vorlauftage_arg, default=3,
                        help="Vorfrist-Vorlauf in Tagen (Default: 3)")
    args = parser.parse_args(argv)

    try:
        report = _lade_report(Path(args.report))
        opts = dict(aktenzeichen=args.aktenzeichen, vorlauftage=args.vorlauftage)

        if args.format == "beide":
            if not args.output_dir:
                raise ExportEingabeFehler("--format beide verlangt --output-dir (zwei Dateien)")
            ziel = Path(args.output_dir)
            try:
                ziel.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ExportEingabeFehler(f"Zielordner nicht anlegbar: {exc}")
            id8 = _identitaet(report, report["kalender_termine"][0], args.aktenzeichen)[:8]
            ics_pfad = ziel / f"ao-frist-{id8}.ics"
            csv_pfad = ziel / f"ao-frist-{id8}.csv"
            _schreibe(ics_pfad, baue_ical(report, **opts))
            _schreibe(csv_pfad, baue_csv(report, **opts))
            print(f"{ics_pfad}\n{csv_pfad}")
            return 0

        inhalt = (baue_ical(report, **opts) if args.format == "ics"
                  else baue_csv(report, **opts))
        if args.output:
            _schreibe(Path(args.output), inhalt)
        else:
            sys.stdout.write(inhalt)
        return 0
    except ExportEingabeFehler as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
