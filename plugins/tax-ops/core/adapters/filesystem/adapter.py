#!/usr/bin/env python3
"""core/adapters/filesystem/adapter — Referenz-Adapter (P2/P3): Datei-Sync
zwischen einer externen Quelle (`--quelle`, z. B. ein Software-Export-Ordner)
und `kontext/` (`--kontext`), gesteuert über ein Mapping (`--mapping`).

Beweist die Agnostik-Garantie des Kontext-Layers (D11a): `kontext/`
funktioniert mit reinen Dateien, unabhängig von jeder Kanzleisoftware. Jeder
künftige Live-Adapter (z. B. ein MCP-Konnektor-Sync) erfüllt denselben
Vertrag: `pull`/`push`, Hash-Manifest für Idempotenz, Konflikt-Handling ohne
stillschweigendes Überschreiben.

Richtungen:
    pull   Quelle  -> kontext/   (externes System ist führend)
    push   kontext/ -> Quelle    (kontext/ ist führend)

Idempotenz (P3, wie core/calc/fristen/kalender_executor.py): Hat sich die
Quelldatei einer Sync-Richtung seit dem letzten Lauf nicht geändert (Hash im
Manifest identisch), wird NICHTS geschrieben — kein Rewrite, kein
Zeitstempel-Rauschen.

Konflikt-Regel (NIEMALS stillschweigend überschreiben): Haben sich seit dem
letzten Sync **beide** Seiten eines Mappings geändert (bzw. gibt es noch
keine Baseline und beide Dateien existieren bereits mit unterschiedlichem
Inhalt), wird die Zieldatei NICHT angefasst. Stattdessen schreibt der
Adapter eine `<ziel>.conflict`-Kopie mit dem neuen Inhalt der Quelle daneben
und trägt den Konflikt in den Report ein. Exit-Code 3, wenn mindestens ein
Konflikt aufgetreten ist.

Mapping-Datei (`--mapping`, JSON):
    {"eintraege": [{"quelle": "Mandate/2026-001/akte.md",
                    "kontext": "mandate/2026-001.md"}, ...]}

Manifest-Datei (`--manifest`, JSON, wird vom Adapter geschrieben/aktualisiert):
    {"eintraege": {"<kontext-relativ>": {"quelle_hash": "sha256:...",
                                         "kontext_hash": "sha256:...",
                                         "letzter_sync": "<ISO-8601>",
                                         "richtung": "pull"}}}

CLI:
    python3 adapter.py pull --quelle DIR --kontext DIR --manifest FILE --mapping FILE [--output REPORT.json]
    python3 adapter.py push --quelle DIR --kontext DIR --manifest FILE --mapping FILE [--output REPORT.json]

Exit-Codes: 0 = synchronisiert (ggf. inkl. unveränderter Einträge), 2 =
Eingabefehler (Mapping/Manifest kaputt, Pflicht-Verzeichnis fehlt), 3 =
mindestens ein Konflikt.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


class AdapterFehler(Exception):
    """Eingabefehler → Exit 2 mit klarer Meldung, nie Traceback."""


# --------------------------------------------------------------------------
# Hash / JSON-Hilfsfunktionen
# --------------------------------------------------------------------------

def _hash_datei(pfad: Path) -> str | None:
    if not pfad.is_file():
        return None
    return "sha256:" + hashlib.sha256(pfad.read_bytes()).hexdigest()


def _jetzt_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _lade_json(pfad: Path, default: Any) -> Any:
    if not pfad.is_file():
        return default
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AdapterFehler(f"{pfad}: kein gültiges JSON: {exc}") from exc


def _lade_mapping(pfad: Path) -> list[dict[str, str]]:
    if not pfad.is_file():
        raise AdapterFehler(f"Mapping-Datei nicht gefunden: {pfad}")
    daten = _lade_json(pfad, None)
    eintraege = daten.get("eintraege") if isinstance(daten, dict) else None
    if not isinstance(eintraege, list) or not eintraege:
        raise AdapterFehler(f"{pfad}: 'eintraege' muss eine nicht-leere Liste sein")
    for i, e in enumerate(eintraege):
        if not isinstance(e, dict) or not e.get("quelle") or not e.get("kontext"):
            raise AdapterFehler(f"{pfad}: Eintrag {i} braucht nicht-leere Felder "
                                f"'quelle' und 'kontext'")
    return eintraege


# --------------------------------------------------------------------------
# Sync-Logik (P3 — die Entscheidung "kopieren / überspringen / Konflikt" ist
# reine Wenn-dann-Logik, kein Modell-Ermessen)
# --------------------------------------------------------------------------

def sync(richtung: str, quelle_dir: Path, kontext_dir: Path,
         mapping: list[dict[str, str]], manifest: dict[str, Any]
         ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eintraege = manifest.setdefault("eintraege", {})
    ergebnisse: list[dict[str, Any]] = []
    konflikte: list[dict[str, Any]] = []
    jetzt = _jetzt_iso()

    for m in mapping:
        rel_quelle, rel_kontext = m["quelle"], m["kontext"]
        key = rel_kontext
        quelle_pfad = quelle_dir / rel_quelle
        kontext_pfad = kontext_dir / rel_kontext

        if richtung == "pull":
            source_pfad, ziel_pfad = quelle_pfad, kontext_pfad
        else:
            source_pfad, ziel_pfad = kontext_pfad, quelle_pfad

        if not source_pfad.is_file():
            ergebnisse.append({"eintrag": key, "status": "quelldatei_fehlt",
                              "hinweis": f"Quelle dieser Sync-Richtung fehlt: {source_pfad}"})
            continue

        source_hash = _hash_datei(source_pfad)
        ziel_hash_vorher = _hash_datei(ziel_pfad)
        baseline = eintraege.get(key)
        baseline_quelle = baseline.get("quelle_hash") if baseline else None
        baseline_kontext = baseline.get("kontext_hash") if baseline else None
        baseline_source = baseline_quelle if richtung == "pull" else baseline_kontext
        baseline_ziel = baseline_kontext if richtung == "pull" else baseline_quelle

        source_geaendert = source_hash != baseline_source
        if not source_geaendert:
            # Idempotenz: Quelle unverändert seit letztem Sync -> nichts zu tun,
            # kein Rewrite (auch dann, wenn das Ziel inzwischen lokal bearbeitet
            # wurde — das ist kein Konflikt, sondern eine lokale Änderung ohne
            # neue eingehende Version).
            ergebnisse.append({"eintrag": key, "status": "unveraendert"})
            continue

        ziel_geaendert = (ziel_hash_vorher != baseline_ziel) if baseline is not None \
            else (ziel_hash_vorher is not None)

        if ziel_geaendert and ziel_hash_vorher != source_hash:
            konflikt_pfad = ziel_pfad.with_name(ziel_pfad.name + ".conflict")
            konflikt_pfad.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_pfad, konflikt_pfad)
            eintrag_konflikt = {"eintrag": key, "konflikt_datei": str(konflikt_pfad),
                                "hinweis": ("beide Seiten seit letztem Sync geändert (oder "
                                           "kein Sync-Verlauf, Ziel weicht ab) — Zieldatei "
                                           f"{ziel_pfad} NICHT überschrieben")}
            konflikte.append(eintrag_konflikt)
            ergebnisse.append({"eintrag": key, "status": "konflikt", **{
                k: v for k, v in eintrag_konflikt.items() if k != "eintrag"}})
            continue

        # Sicher: Quelle -> Ziel kopieren (Ziel unverändert seit letztem Sync
        # bzw. identisch mit der neuen Quelle).
        ziel_pfad.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_pfad, ziel_pfad)
        # Nach der Kopie sind beide Seiten byte-identisch -> derselbe Hash.
        eintraege[key] = {
            "quelle_hash": source_hash,
            "kontext_hash": source_hash,
            "letzter_sync": jetzt,
            "richtung": richtung,
        }
        ergebnisse.append({"eintrag": key, "status": "synchronisiert"})

    return ergebnisse, konflikte


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _pflicht_verzeichnis(pfad: Path, *, anlegen: bool, bezeichnung: str) -> None:
    if pfad.is_dir():
        return
    if anlegen:
        pfad.mkdir(parents=True, exist_ok=True)
        return
    raise AdapterFehler(f"{bezeichnung} existiert nicht: {pfad}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="richtung", required=True)
    for name in ("pull", "push"):
        p = sub.add_parser(name, help=f"{name}: siehe Modulbeschreibung")
        p.add_argument("--quelle", required=True, help="externes Quell-Verzeichnis")
        p.add_argument("--kontext", required=True, help="kontext/-Verzeichnis")
        p.add_argument("--manifest", required=True,
                       help="Hash-Manifest (JSON, wird angelegt/aktualisiert)")
        p.add_argument("--mapping", required=True,
                       help="Mapping-Datei (JSON, siehe Modulbeschreibung)")
        p.add_argument("--output", help="Zieldatei für den JSON-Report (Default: stdout)")
    args = parser.parse_args(argv)

    quelle_dir = Path(args.quelle)
    kontext_dir = Path(args.kontext)

    try:
        # pull: Quelle ist führend -> muss existieren; kontext/ darf frisch
        # entstehen. push: umgekehrt.
        _pflicht_verzeichnis(quelle_dir, anlegen=(args.richtung == "push"),
                            bezeichnung="--quelle")
        _pflicht_verzeichnis(kontext_dir, anlegen=(args.richtung == "pull"),
                            bezeichnung="--kontext")
        mapping = _lade_mapping(Path(args.mapping))
        manifest_pfad = Path(args.manifest)
        manifest = _lade_json(manifest_pfad, {"eintraege": {}})
        if not isinstance(manifest, dict):
            raise AdapterFehler(f"{manifest_pfad}: Manifest muss ein JSON-Objekt sein")
    except AdapterFehler as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2

    ergebnisse, konflikte = sync(args.richtung, quelle_dir, kontext_dir, mapping, manifest)

    manifest_pfad.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")

    report = {
        "meta": {
            "erzeugt_von": "plugins/legal-ops/core/adapters/filesystem/adapter.py",
            "richtung": args.richtung,
            "quelle_dir": str(quelle_dir),
            "kontext_dir": str(kontext_dir),
            "manifest_datei": str(manifest_pfad),
            "quelle": "executor",
        },
        "ergebnisse": ergebnisse,
        "anzahl_konflikte": len(konflikte),
        "konflikte": konflikte,
    }
    ausgabe = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(ausgabe + "\n", encoding="utf-8")
    else:
        print(ausgabe)

    if konflikte:
        print(f"\nAdapter: {len(konflikte)} Konflikt(e) — .conflict-Datei(en) geschrieben, "
              f"Zieldatei(en) NICHT überschrieben", file=sys.stderr)
        return 3
    print(f"Adapter: {args.richtung} abgeschlossen ({len(ergebnisse)} Eintrag/Einträge, "
          f"0 Konflikte)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
