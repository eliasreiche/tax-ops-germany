# tax-ops-germany — Non-Billable Library für deutsche Steuerkanzleien

[![CI](https://github.com/eliasreiche/tax-ops-germany/actions/workflows/ci.yml/badge.svg)](https://github.com/eliasreiche/tax-ops-germany/actions/workflows/ci.yml)

Open-Source-Library aus **Claude-Skills und deterministischen Python-Executors**
für die **non-billable Workflows** deutscher Steuerkanzleien — Aufgaben
organisieren, Fristen und Vergütung nach Gesetz/Tabelle berechnen, Entwürfe
formulieren. Schwesterprojekt von
[`legal-ops-germany`](https://github.com/eliasreiche/legal-ops-germany) für
Rechtsanwaltskanzleien, gleiche Architektur und Prinzipien. Funktionsweise
ausschließlich nach deutschem Recht.

> Dieses Projekt ist nicht mit Anthropic PBC verbunden, wird von ihr nicht
> unterstützt oder gesponsert. Claude und Anthropic sind Marken der
> Anthropic PBC.

> **Work-in-progress.** Skills folgen ab Welle 6 (siehe
> [Skill-Übersicht](#skill-übersicht-geplant)) — aktuell ist dies das
> Gerüst: Plugin-Struktur, geteilte Rechner (Snapshot aus
> `legal-ops-germany`), Struktur-Lint, Install-Smoke-Test, CI.

## Keine Hilfeleistung in Steuersachen

Diese Library ist **kein geprüftes Produkt** und ersetzt keine steuerliche
Beratung. Die Skills organisieren Abläufe und rechnen nach Gesetz oder
Tabelle — sie subsumieren nicht. Konkret:

- **Organisatorisch, nicht materiell** — Skills sortieren, terminieren und
  formulieren Entwürfe. Die steuerliche Würdigung eines Sachverhalts bleibt
  in jedem Fall beim Berufsträger (§§ 3, 5 StBerG).
- **Verschwiegenheit** — Mandantendaten unterliegen § 57 StBerG und § 203
  StGB. Modellzugang und Datenhaltung müssen das einhalten; die Kanzlei
  prüft das vor jedem Einsatz selbst.
- **Dienstleister-Einsatz** — externe Hilfspersonen/Tools bei der
  Hilfeleistung in Steuersachen sind nur im Rahmen des § 62a StBerG zulässig
  (Verpflichtung auf Verschwiegenheit, Auswahl- und Kontrollpflicht).

Jedes Ergebnis unterliegt der Zweitkontrolle durch die Kanzlei (P5, unten).

## Fünf Grundprinzipien

- **P1 — Zahlen deterministisch.** Alles mit Zahlen, Daten, Fristen oder
  Geld rechnet ein Python-Executor mit nachvollziehbarer Rechenkette
  (`RechenSchritt`) — nie das Modell.
- **P2 — Text nur als Entwurf.** Skills, die Schreiben oder Mitteilungen
  formulieren, erzeugen Entwürfe. Kein Skill versendet automatisch —
  Versand ist immer Kanzlei-Entscheidung.
- **P3 — Provenienz.** Modell-extrahierte Werte (aus Dokumenten, E-Mails)
  sind als solche gekennzeichnet und laufen durchs Provenienz-Gate
  (`core/verify/provenienz.py`), bevor sie in eine Rechenkette einfließen.
- **P4 — Dateibasiert.** Jeder Skill arbeitet über Datei-Schnittstellen
  (CSV, PDF, EML, iCal, DOCX) — kein Live-Zugriff auf DATEV oder andere
  Kanzleisoftware. Live-Anbindung läuft, wo vorhanden, ausschließlich über
  den Kontext-Layer (`kontext/`) und dokumentierte Adapter.
- **P5 — Zweitkontrolle.** Jeder Skill dokumentiert im Frontmatter seine
  berufsrechtliche Einordnung (`stberg_einordnung`), Datenhinweise und
  Haftungsgrenzen (Berufsrechts-Gate, vom Struktur-Lint erzwungen) — kein
  Ergebnis ersetzt die Prüfung durch die Kanzlei.

## Reifegrad

- 🚧 `Work-in-progress` — noch nicht entwickelt (Stub) oder Code ohne
  Test-Run.
- 🧪 `beta` — automatisierte Tests laufen grün in CI, noch keine
  Live-Abnahme.
- ✅ `getestet` — händische Abnahme durch den Maintainer (Datum im
  Frontmatter, `haendisch_getestet`) — keine Production-Garantie.

Ein Status wird nie übersprungen dokumentiert: `getestet` setzt inhaltlich
`beta` voraus. Details: [CONVENTIONS.md](CONVENTIONS.md).

## Skill-Übersicht (geplant)

Skills folgen ab Welle 6 — noch keiner ist implementiert. Geplanter Fahrplan:

| Skill | Welle | Bereich |
|---|---|---|
| `ao-fristenrechner` | 6 | `fristen` |
| `stbvv-rechner` | 6 | `verguetung` |
| `aufgaben-triage` | 6 | `mandant` |
| `auswertungs-versand` | 7 | `mandant` |
| `bescheid-pruefer` | 7 | `mandant` |
| `gestaltungswissen` | 7 | `wissen` |
| `mandanten-fristenkalender` | 8 | `fristen` |
| `belege-vollstaendigkeit` | 8 | `posteingang` |
| `erechnung-pruefer` | 8 | `posteingang` |

### Ebenfalls für Steuerkanzleien nutzbar (aus legal-ops-germany)

Steuerberater sind Verpflichtete nach § 2 Abs. 1 Nr. 12 GwG — folgende
Skills aus [`legal-ops-germany`](https://github.com/eliasreiche/legal-ops-germany)
sind branchenunabhängig und direkt einsetzbar:

- `gwg-risiko-check`, `gwg-live-screening` — GwG-Risikoklassifizierung und
  Sanktionslisten-Screening.
- `honorar-mahnwesen` — OPOS-Mahnwesen.
- `passive-zeiterfassung` — Zeiterfassung aus Kalender-/E-Mail-Metadaten.
- `email-akten-zuordnung` — E-Mail-Akten-Zuordnung.
- `kontext-sync` — Sync des Kontext-Layers (M365-MCP oder Datei-Adapter).

### Status-Tabelle dieses Repos (automatisch generiert)

<!-- skill-status:start -->
| Skill | Bereich | Welle | Status |
|---|---|---|---|
| [`ao-fristenrechner`](plugins/tax-ops/skills/ao-fristenrechner/SKILL.md) | `fristen` | 6 | 🧪 `beta` |
| [`aufgaben-triage`](plugins/tax-ops/skills/aufgaben-triage/SKILL.md) | `posteingang` | 6 | 🧪 `beta` |
| [`stbvv-rechner`](plugins/tax-ops/skills/stbvv-rechner/SKILL.md) | `verguetung` | 6 | 🧪 `beta` |
<!-- skill-status:ende -->

## Wie es funktioniert

- **Claude orchestriert, Python rechnet** — siehe P1. Executors liegen unter
  [`plugins/tax-ops/core/calc/`](plugins/tax-ops/core/calc/).
- **Datei rein, Datei raus** — siehe P4.
- **Kontext-Layer** — ein per-Kanzlei-Ordner `kontext/` ist die einzige
  Schnittstelle der Skills zu Kanzlei-Wissen (Mandate, Kontakte,
  Kanzlei-Profil). Details: [`core/context/README.md`](plugins/tax-ops/core/context/README.md).
- **Berufsrechts-Gate** — jeder Skill dokumentiert im Frontmatter
  `stberg_einordnung`, `daten_hinweis` und `haftung` — vom
  [Struktur-Lint](plugins/tax-ops/core/verify/struktur_lint.py) erzwungen.

## Verhältnis zu legal-ops-germany

`tax-ops-germany` ist das Schwesterprojekt von
[`legal-ops-germany`](https://github.com/eliasreiche/legal-ops-germany)
(gleicher Autor, gleiche Architektur; dort Apache-2.0, hier GPL-3.0-or-later). `plugins/tax-ops/core/`
ist ein **Snapshot** der branchenunabhängigen Rechen-/Verifikationsmodule aus
`legal-ops-germany` @ Commit `622ddd0` — kein automatischer Sync, siehe
[`core/VENDORED.md`](plugins/tax-ops/core/VENDORED.md). Steuerspezifische
Rechner (AO-Fristen, StBVV) entstehen hier neu.

## Nutzung

Voraussetzung ist ein datenschutzkonformer Claude-Zugang der Kanzlei (z. B.
Claude Code / Cowork über AWS Bedrock, Region Frankfurt).

**Weg 1 — mit Git (empfohlen, bekommt Updates):** in Claude Code

```
/plugin marketplace add eliasreiche/tax-ops-germany
/plugin install tax-ops@tax-ops-germany
```

Aktualisieren später mit `claude plugin marketplace update tax-ops-germany`.

**Weg 2 — per ZIP in der Claude-Desktop-App (ohne Git, ohne Terminal):** auf
der [Releases-Seite](https://github.com/eliasreiche/tax-ops-germany/releases)
beim aktuellen Release die Datei **`tax-ops-vX.Y.Z.zip`** laden (nicht
„Source code"), dann in der Claude-App unter **Anpassen** das ZIP hochladen.
Das ZIP enthält das Plugin direkt (`.claude-plugin/plugin.json` an der
Wurzel, `core/` und `skills/`), fertig zum Hochladen.

> Die ZIP-Installation ist ein **eingefrorener Stand** — sie aktualisiert
> sich nicht. Für einen neuen Stand das ZIP des neuesten Release laden und
> erneut hochladen.

### Release-Konvention

Version in `plugin.json` **und** `marketplace.json` gemeinsam heben, Tag
`vX.Y.Z`, Release-Asset per `git archive vX.Y.Z:plugins/tax-ops` (an jedes
Release als `tax-ops-vX.Y.Z.zip` anhängen).

## Entwicklung

```bash
python3 plugins/tax-ops/core/verify/struktur_lint.py   # Struktur-Lint (Berufsrechts-Gate + Containment)
pip install pytest && pytest -q                         # Tests (inkl. Install-Smoke-Test)
```

## Lizenz

[GPL-3.0-or-later](LICENSE) · Attributionen: [NOTICE](NOTICE). Der `core/`-Snapshot stammt aus dem Apache-2.0-lizenzierten `legal-ops-germany` (kompatibel, siehe NOTICE).
