# CONVENTIONS — Hausregeln

Verbindlich für jeden Skill, Executor und jede Doku-Seite in diesem Repo.
Der [Struktur-Lint](plugins/tax-ops/core/verify/struktur_lint.py) erzwingt
die maschinenprüfbaren Teile in CI. Schwesterprojekt von
[`legal-ops-germany`](https://github.com/eliasreiche/legal-ops-germany) —
gleiche Grundsätze, angepasst auf das Berufsrecht der Steuerberater.

## Sprache & Zielgruppe

- **Deutsch** ist die Arbeits- und Doku-Sprache (Zielgruppe: deutsche
  Steuerkanzleien).
- Fachbegriffe (AO, StBVV, GwG, DATEV, ELSTER) werden nicht übersetzt.

## KISS-Grundsatz

Ein Skill tut eine Sache. Kein Skill baut eine eigene DATEV-/ELSTER-Live-
Integration — Datei-Schnittstelle immer, Konnektor nur über den
Kontext-Layer und dokumentierte Adapter (siehe P4 im
[README](README.md#fünf-grundprinzipien)).

## Skill-Frontmatter (Pflichtfelder)

```yaml
---
name: <verzeichnisname>            # muss dem Ordnernamen entsprechen
description: "Was der Skill tut + wann er triggert (Skill-Discovery)."
status: Work-in-progress | beta | getestet   # Reifegrad-Leiter, siehe unten
welle: 6-8                         # Build-Reihenfolge
bereich: <bereich>                 # siehe Liste unten
stberg_einordnung: "Eine von drei Kategorien, siehe unten."
daten_hinweis: "Welche Daten hinein dürfen; § 57 StBerG / § 203 StGB / DSGVO-konformer Modellzugang."
haftung: "Zweitkontroll-Klausel; bei Fristen/Vergütung zwingend."
haendisch_getestet: JJJJ-MM-TT     # nur bei status: getestet (Pflicht, Datum der Abnahme)
---
```

### `bereich` — zulässige Werte

`fristen` · `verguetung` · `posteingang` · `mandant` · `compliance` ·
`wissen` · `querschnitt`

### `stberg_einordnung` — drei Kategorien

Jeder Skill trägt genau eine der folgenden Einordnungen:

1. **„organisatorisch, keine Hilfeleistung"** — der Skill sortiert,
   terminiert oder verteilt, ohne einen steuerlichen Sachverhalt zu würdigen
   (z. B. Aufgaben-Triage, Belege-Vollständigkeitscheck).
2. **„Rechnen nach Tabelle/Gesetz ohne Subsumtion"** — der Skill berechnet
   deterministisch nach einer festen Formel oder Tabelle (Fristen, StBVV-
   Gebühren) — trifft keine Wertung, wendet nur an.
3. **„Hilfeleistung i. S. § 3 StBerG — nur durch Berufsträger nutzbar"** —
   der Skill berührt eine steuerliche Würdigung (z. B. Gestaltungswissen,
   Bescheid-Prüfung mit Einspruchsempfehlung); Output ist immer Entwurf,
   Nutzung nur durch den Berufsträger selbst.

### Reifegrad-Leiter

| Status | Bedeutung | Lint-Voraussetzung |
|---|---|---|
| 🚧 `Work-in-progress` | noch nicht entwickelt (Stub) **oder** Code ohne Test-Run | — |
| 🧪 `beta` | gegen Testdaten getestet, Tests laufen grün in CI | echte Dateien in `tests/` |
| ✅ `getestet` | live (händisch) getestet durch den Maintainer — keine Production-Garantie | wie `beta` + `haendisch_getestet: <Datum>` |

Ein Status wird nie übersprungen dokumentiert: `getestet` setzt inhaltlich
`beta` voraus.

## Naming-Konvention für Skill-Slugs

Der Ordnername unter `plugins/tax-ops/skills/` (== `name:`-Frontmatter,
Lint-erzwungen): deutschsprachig, Funktion statt Implementierung
(`stbvv-rechner`, nicht `stbvv-calculator`), kein `-de`-Suffix (der Scope
des Repos ist bereits deutsch), kein `-light`-Suffix (Reifegrad steht im
Frontmatter, nicht im Namen).

## Executor-Kontrakt

Jeder Executor ist ein eigenständiges CLI-Skript (nur Stdlib):

- Eingabe über `--input <datei.json>` (oder skillspezifisch benannte
  Datei-Flags), Ausgabe als JSON auf stdout oder über `--output <datei>`.
- Exit-Codes: `0` sauber, `1` fachlicher Fehler/Schema-Verstoß, `2`
  Eingabefehler (Datei fehlt, ungültiges JSON).
- Jede Rechenkette besteht aus `RechenSchritt`-Einträgen
  (`plugins/tax-ops/core/calc/rechenschritt.py`) mit `quelle: "executor"` —
  Claude liest nur das Ergebnis, entscheidet nie selbst über Zahlen (P1).

## Anti-Halluzination

- Kein Skill erfindet Aktenzeichen, Beträge, Daten oder Normzitate. Fehlende
  Angaben werden als **Lücke** ausgewiesen, nie ergänzt.
- Modell-extrahierte Werte laufen durchs Provenienz-Gate
  (`core/verify/provenienz.py`, P3), bevor sie in eine Rechenkette
  einfließen.
- Skills, die Schreiben draften, erzeugen **Entwürfe** — Versand ist immer
  Kanzlei-Entscheidung (P2).

## Release-Konvention

Version in `plugins/tax-ops/.claude-plugin/plugin.json` **und**
`.claude-plugin/marketplace.json` gemeinsam heben, Git-Tag `vX.Y.Z`,
Release-Asset `tax-ops-vX.Y.Z.zip` = `git archive vX.Y.Z:plugins/tax-ops`.

## Was dieses Repo nicht ist

Keine Steuerberatung, kein Hosting, keine DATEV-/ELSTER-Live-Integration
(nur Datei-Brücken über den Kontext-Layer).
