# Plugin `tax-ops`

Ein einziges Plugin bündelt alle Skills **und** die geteilten Rechner/Verifier
unter `core/`. So umschließt die Plugin-Grenze (`plugins/tax-ops/`) den
`core/`-Baum — beim Install landen Executors und ihre Rechenkerne gemeinsam im
Cache, jeder Executor-Skill ist im Auslieferungszustand lauffähig.

Executor-Aufrufe in den SKILL.md adressieren plugin-relativ über
`${CLAUDE_PLUGIN_ROOT}` (absoluter Pfad zum installierten Plugin-Verzeichnis) —
kein Aufruf setzt ein bestimmtes Arbeitsverzeichnis voraus.

## Prozessbereiche

Skills folgen mit Welle 6 (siehe [`skills/README.md`](skills/README.md)) und
werden fachlich nach sieben Prozesskategorien gegliedert (Feld `bereich:` im
Frontmatter; die Auslieferung bleibt ein Plugin). `core/` ist ein Snapshot aus
`legal-ops-germany`, siehe [`core/VENDORED.md`](core/VENDORED.md). Hausregeln:
[CONVENTIONS.md](https://github.com/eliasreiche/tax-ops-germany/blob/main/CONVENTIONS.md).
