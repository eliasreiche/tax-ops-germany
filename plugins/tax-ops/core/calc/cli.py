#!/usr/bin/env python3
"""cli — gemeinsamer Ablauf der Executor-Kommandozeilen (P2).

Jeder Rechen-Executor in `core/calc/` hat denselben Rahmen: `--input`
(JSON-Anfrage) einlesen, Report bauen, als JSON nach `--output` schreiben
oder auf stdout ausgeben, jeder Eingabefehler wird zu `Fehler: …` auf stderr
und Exit 2 — nie ein Traceback. Dieser Rahmen steht hier einmal statt je
Executor.

Die fachliche Arbeit (`baue_report()`) und die Fehlerklassen bleiben beim
jeweiligen Executor — dies hier ist nur die CLI-Mechanik.

Nur Standardbibliothek.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class CliFehler(ValueError):
    """Eingabe-/Ausgabefehler der CLI → Exit 2 mit klarer Meldung."""


def standard_parser(beschreibung: str | None,
                    input_hilfe: str = "JSON-Eingabedatei",
                    output_hilfe: str = "Zieldatei für den JSON-Report (Default: stdout)"
                    ) -> argparse.ArgumentParser:
    """Parser mit `--input` (Pflicht) und `--output` (optional)."""
    parser = argparse.ArgumentParser(
        description=beschreibung,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, help=input_hilfe)
    parser.add_argument("--output", help=output_hilfe)
    return parser


def pflichtfeld(eingabe: dict[str, Any], feld: str, kontext: str | None = None, *,
                fehler: type[Exception] = CliFehler) -> Any:
    """Wert eines Pflichtfelds; fehlend/leer ist ein Fehler, kein Default.

    `fehler` ist die Fehlerklasse des aufrufenden Executors — die Aufrufer
    binden sie einmal per `functools.partial`.
    """
    if feld not in eingabe or eingabe[feld] in (None, ""):
        name = f"{kontext}.{feld}" if kontext else feld
        raise fehler(f"Pflichtfeld '{name}' fehlt oder ist leer")
    return eingabe[feld]


def lese_json_objekt(pfad: Path) -> dict[str, Any]:
    """Liest eine JSON-Datei, die ein Objekt enthalten muss."""
    if not pfad.is_file():
        raise CliFehler(f"Eingabedatei nicht gefunden: {pfad}")
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliFehler(f"Eingabedatei ist kein gültiges JSON: {exc}")
    if not isinstance(daten, dict):
        raise CliFehler("Eingabe muss ein JSON-Objekt sein")
    return daten


def schreibe_report(report: dict[str, Any], output: str | None) -> None:
    """Schreibt den Report nach `output` (JSON, UTF-8) oder auf stdout."""
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        try:
            Path(output).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            raise CliFehler(f"Report-Datei kann nicht geschrieben werden: {exc}")
    else:
        print(text)
