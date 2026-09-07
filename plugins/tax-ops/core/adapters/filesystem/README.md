# core/adapters/filesystem — Referenz-Adapter

Synchronisiert Dateien zwischen einem externen Quell-Ordner (Export einer
Kanzleisoftware oder eines anderen Systems) und `kontext/`, gesteuert über ein
Mapping. Beweist die Agnostik-Garantie (D11a): `kontext/` funktioniert mit
reinen Dateien — jeder künftige Live-Adapter erfüllt denselben Vertrag.

Fähigkeiten: Dokumente in beide Richtungen (`pull` und `push`) — keine
Kalender-, keine Mail-Daten.

## CLI

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/core/adapters/filesystem/adapter.py pull \
  --quelle <externer-export-ordner> --kontext <kontext-verzeichnis> \
  --manifest <manifest.json> --mapping <mapping.json>

python3 ${CLAUDE_PLUGIN_ROOT}/core/adapters/filesystem/adapter.py push \
  --quelle <externer-export-ordner> --kontext <kontext-verzeichnis> \
  --manifest <manifest.json> --mapping <mapping.json>
```

- **`pull`** — externes System ist führend, überträgt nach `kontext/`.
- **`push`** — `kontext/` ist führend, überträgt zurück in den externen Ordner.

## Mapping (`--mapping`, JSON)

```json
{
  "eintraege": [
    {"quelle": "Mandate/2026-001/akte.md", "kontext": "mandate/2026-001.md"},
    {"quelle": "Kontakte/kontakte.csv", "kontext": "kontakte.md"}
  ]
}
```

Jeder Eintrag ist ein Dateipaar: `quelle` relativ zu `--quelle`, `kontext`
relativ zu `--kontext`.

## Manifest (`--manifest`, JSON — wird vom Adapter geschrieben)

```json
{
  "eintraege": {
    "mandate/2026-001.md": {
      "quelle_hash": "sha256:...",
      "kontext_hash": "sha256:...",
      "letzter_sync": "2026-07-13T12:00:00Z",
      "richtung": "pull"
    }
  }
}
```

Hält je Mapping-Eintrag die Hashes beider Seiten zum Zeitpunkt des letzten
erfolgreichen Syncs fest — Grundlage für Idempotenz und Konflikterkennung.

## Idempotenz

Ist die Quelldatei der aktuellen Richtung seit dem letzten Sync unverändert
(Hash == Manifest-Eintrag), passiert **nichts** — kein Rewrite, kein
Zeitstempel-Rauschen.

## Konflikte — niemals stillschweigend überschreiben

Haben sich seit dem letzten Sync **beide** Seiten geändert (oder gibt es noch
keinen Sync-Verlauf und beide Dateien existieren bereits mit
unterschiedlichem Inhalt), wird die Zieldatei **nicht** angefasst:

- eine `<ziel>.conflict`-Datei mit dem neuen Inhalt der Quelle wird daneben
  geschrieben,
- der Report führt den Konflikt unter `konflikte[]` auf,
- der Prozess endet mit **Exit-Code 3** (nach Verarbeitung aller
  Mapping-Einträge — ein Konflikt stoppt nicht die übrigen Einträge).

Die Kanzlei entscheidet die Zusammenführung händisch; der Adapter rät nie.

## Exit-Codes

| Code | Bedeutung |
|---|---|
| `0` | Synchronisiert (inkl. ggf. unveränderter Einträge), keine Konflikte. |
| `2` | Eingabefehler — Mapping/Manifest kaputt, Pflicht-Verzeichnis fehlt (`--quelle` bei `pull`, `--kontext` bei `push`). |
| `3` | Mindestens ein Konflikt — `.conflict`-Dateien geschrieben, Zieldateien nicht überschrieben. |

## Bewusste Grenzen

- **Kein Merge** — der Adapter erkennt Konflikte, löst sie aber nie
  automatisch auf.
- **Keine Löschung** — verschwindet eine Quelldatei, meldet der Adapter
  `quelldatei_fehlt` für den betroffenen Eintrag, löscht aber nichts auf der
  Zielseite.
- **Byte-Vergleich, kein semantischer Diff** — zwei inhaltsgleiche, aber
  byte-unterschiedliche Exporte (z. B. andere Zeilenenden) gelten als
  „geändert".
