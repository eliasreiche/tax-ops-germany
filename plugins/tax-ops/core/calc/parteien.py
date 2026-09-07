#!/usr/bin/env python3
"""parteien — CSV-Einlesen von Partei-Listen (P2, Datei-Schnittstelle).

Zwei Skills lesen dieselbe Art Datei: `interessenkollision-check` die
Mandanten-/Gegnerliste und die neuen Parteien, `gwg-live-screening` die zu
screenenden Parteien. Format und Fehlerdisziplin sind identisch —
Semikolon-getrennt, UTF-8 (BOM toleriert), Kopfzeile Pflicht, `name` je Zeile
Pflicht, leere Datei ist ein Fehler. Das steht deshalb hier einmal.

Was sich unterscheidet, kommt vom Aufrufer:

  * die **Fehlerklasse** (`fehler=`) — jeder Executor wirft seine eigene und
    fängt sie in `main()` zu Exit 2 ab;
  * die **Pflichtspalten** über `name` hinaus;
  * die **Zusatzfelder** je Zeile (`zusatz=`) — `interessenkollision-check`
    validiert dort Rolle und Typ gegen seine Wertelisten,
    `gwg-live-screening` übernimmt `typ` ungeprüft.

JSON-Eingaben bleiben skill-lokal: die beiden Skills akzeptieren
unterschiedliche Strukturen (nur Objekte vs. Objekte **und** Namens-Strings).

Nur Standardbibliothek. Liest nur, schreibt nie.
"""
from __future__ import annotations

import csv
import io
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Partei:
    """Eine Partei. `rolle`/`typ`/`az`/`notiz` sind optional — welche davon ein
    Skill füllt und validiert, entscheidet sein `zusatz`-Callback."""
    name: str
    rolle: str | None = None
    typ: str | None = None
    az: str | None = None
    notiz: str | None = None


def lese_csv_zeilen(pfad: Path, fehler: type[Exception]
                    ) -> tuple[list[str], list[dict[str, str]]]:
    """(Spaltennamen, Zeilen als Dicts) — Werte und Header getrimmt."""
    try:
        text = pfad.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise fehler(f"{pfad}: keine gültige UTF-8-Datei ({exc})") from exc
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    fieldnames = [h.strip() for h in (reader.fieldnames or [])]
    if not fieldnames:
        raise fehler(f"{pfad}: CSV ist leer oder hat keine Kopfzeile")
    zeilen = [{(h or "").strip(): (v or "").strip() if v is not None else ""
               for h, v in zeile.items()} for zeile in reader]
    return fieldnames, zeilen


def lese_parteien_csv(pfad: Path, *, fehler: type[Exception],
                      zusatz: Callable[[dict[str, str], str], dict[str, Any]],
                      pflichtspalten: tuple[str, ...] = ("name",)) -> list[Partei]:
    """Partei-Liste aus einer CSV. `zusatz(zeile, ort)` liefert die optionalen
    Felder der Partei (und validiert sie); `ort` ist die Fundstelle für
    Fehlermeldungen (`"Zeile 7"`)."""
    fieldnames, zeilen = lese_csv_zeilen(pfad, fehler)
    fehlend = [s for s in pflichtspalten if s not in fieldnames]
    if fehlend:
        vorhanden = ", ".join(fieldnames)
        if len(pflichtspalten) == 1:
            raise fehler(f"{pfad}: Pflichtspalte '{fehlend[0]}' fehlt "
                         f"(vorhanden: {vorhanden})")
        raise fehler(f"{pfad}: Pflichtspalte(n) fehlen: {', '.join(fehlend)} "
                     f"(vorhanden: {vorhanden})")

    parteien: list[Partei] = []
    for i, zeile in enumerate(zeilen, start=2):  # Zeile 1 = Kopfzeile
        ort = f"Zeile {i}"
        name = zeile.get("name", "")
        if not name:
            raise fehler(f"{pfad}, {ort}: Pflichtfeld 'name' fehlt oder ist leer")
        parteien.append(Partei(name=name, **zusatz(zeile, ort)))
    if not parteien:
        raise fehler(f"{pfad}: keine Einträge (nur Kopfzeile)")
    return parteien
