#!/usr/bin/env python3
"""core/context/validator — CLI-Executor (P2/P3): prüft `kontext/` gegen das Schema.

Prüft entweder ein ganzes `kontext/`-Verzeichnis (`--kontext DIR`) oder eine
einzelne Mandats-Datei (`--datei mandate/<az>.md`) gegen den Kontrakt aus
`core/context/README.md` / `schema.py`:

  * Pflichtfelder im Frontmatter (`az`, `mandant`, `stand`), ISO-Datumsformate,
    `status`-Enum, `streitwert`/`mandatsende` Zahl-oder-null,
  * Pflicht-Abschnitte (`## Parteien`, `## Kommunikation`, `## Letzter Schritt`,
    `## Nächste Frist`),
  * Verweis-Integrität relativer Markdown-Links (nur Warnung, kein Fehler —
    ein Link kann auf ein Dokument zeigen, das (noch) nicht im Repo/Export
    liegt, z. B. ein e-Akte-Verweis außerhalb von `kontext/`).

Die Prüfung selbst ist reine Wenn-dann-Logik in `schema.py` (P3) — dieses
Skript ist nur die CLI-Hülle (Argumente, Exit-Codes, JSON-Report).

CLI:
    python3 validator.py --kontext KONTEXT_DIR [--output REPORT.json]
    python3 validator.py --datei mandate/2026-001.md [--output REPORT.json]

Exit-Codes: 0 = sauber, 1 = Schema-Fehler, 2 = Eingabefehler (Ziel existiert
nicht).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parent  # core/context
if str(_SKILL_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR.parent))

from context.schema import (  # noqa: E402
    KontextEingabeFehler, pruefe_kontext_verzeichnis, pruefe_mandat_datei)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ziel_gruppe = parser.add_mutually_exclusive_group(required=True)
    ziel_gruppe.add_argument("--kontext", help="kontext/-Verzeichnis prüfen (kanzlei.md, "
                             "kontakte.md, mandate/*.md)")
    ziel_gruppe.add_argument("--datei", help="einzelne Mandats-Markdown-Datei prüfen")
    parser.add_argument("--output", help="Zieldatei für den JSON-Report (Default: stdout)")
    args = parser.parse_args(argv)

    try:
        if args.kontext:
            ziel = Path(args.kontext)
            if not ziel.is_dir():
                print(f"Fehler: --kontext ist kein Verzeichnis: {ziel}", file=sys.stderr)
                return 2
            fehler, warnungen, anzahl = pruefe_kontext_verzeichnis(ziel)
            geprueft = str(ziel)
        else:
            ziel = Path(args.datei)
            if not ziel.is_file():
                print(f"Fehler: --datei nicht gefunden: {ziel}", file=sys.stderr)
                return 2
            fehler, warnungen = pruefe_mandat_datei(ziel)
            anzahl = 1
            geprueft = str(ziel)
    except KontextEingabeFehler as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2

    report = {
        "meta": {
            "erzeugt_von": "plugins/legal-ops/core/context/validator.py",
            "geprueft": geprueft,
            "quelle": "executor",
        },
        "ok": len(fehler) == 0,
        "anzahl_dateien_geprueft": anzahl,
        "fehler": fehler,
        "warnungen": warnungen,
    }
    ausgabe = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(ausgabe + "\n", encoding="utf-8")
    else:
        print(ausgabe)

    if fehler:
        print(f"\nKontext-Validator: {len(fehler)} Schema-Fehler", file=sys.stderr)
        for f in fehler:
            print(f"  ✗ {f}", file=sys.stderr)
        return 1
    print(f"Kontext-Validator: sauber ({anzahl} Datei(en) geprüft, "
          f"{len(warnungen)} Warnung(en))", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
