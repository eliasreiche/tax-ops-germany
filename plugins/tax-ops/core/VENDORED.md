# core/ — Snapshot aus legal-ops-germany

Dieser `core/`-Baum ist ein **Snapshot** aus
[`eliasreiche/legal-ops-germany`](https://github.com/eliasreiche/legal-ops-germany)
@ Commit [`622ddd0`](https://github.com/eliasreiche/legal-ops-germany/commit/622ddd0),
gezogen am 2026-09-08 (D23). Gleicher Autor; Quelle steht unter Apache-2.0, dieses Repo unter GPL-3.0-or-later (Apache-2.0 ist in GPL-3.0 einbindbar).

## Übernommene Module

| Modul | Zweck |
|---|---|
| `calc/cli.py` | Gemeinsame CLI-Bausteine für Executor-Skripte. |
| `calc/datum.py` | Datums-Parsing/-Kanonisierung (ISO, deutsch ausgeschrieben, RFC-2822). |
| `calc/rechenschritt.py` | `RechenSchritt`-Datenklasse für nachvollziehbare Rechenketten. |
| `calc/slug.py` | Slug-Normalisierung. |
| `calc/parteien.py` | Parteien-/Mandantenlisten-Parsing (CSV/JSON). |
| `calc/feiertage/` | Gesetzliche Feiertage aller 16 Bundesländer (Gaußsche Osterformel). |
| `calc/matching/` | Fuzzy-Matching, Kölner Phonetik, Namens-Normalisierung, Vergleich. |
| `calc/zuordnung/` | Dokument-Metadaten → Mandats-Kandidaten (Az-Suche, Parteisuche, Kombination). |
| `verify/provenienz.py` | Provenienz-Gate gegen modell-halluzinierte Datumsangaben. |
| `verify/struktur_lint.py` | Struktur-Lint (Frontmatter-Pflichtfelder, Containment-Gate) — auf `tax-ops` angepasst. |
| `context/` | Kontext-Layer (`kontext/`-Ordnerschema, Validator, Beispiel-Fixture). |
| `adapters/filesystem/` | Datei-Referenzadapter für den Kontext-Layer (pull/push, Hash-Manifest). |

## Bewusst nicht übernommen

`calc/fristen`, `calc/rvg`, `calc/gkg`, `calc/gwg`, `calc/opos`, `calc/extf`,
`calc/retention`, `calc/zeit`, `calc/wertgebuehr_formel.py` — Rechtsgebiets-
spezifisch für `legal-ops-germany` (RVG/GKG/ZPO/GwG-Meldewesen). Steuerspezifische
Rechner (AO-Fristen, StBVV) entstehen in `tax-ops` neu, ab Welle 6.

## Sync-Politik

Snapshot ohne Sync-Automatik; Fixes in geteilten Modulen bewusst beidseitig
einspielen (D23).
