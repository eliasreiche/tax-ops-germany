# core/context — der `kontext/`-Ordner (D11, D19)

Der Kontext-Layer löst den Kontextbruch zwischen Claude-Skills und dem
Kanzlei-Wissen (Mandate, Parteien, Termine, Kontakte): ein per-Kanzlei-Ordner
`kontext/` ist die **einzige** Schnittstelle. Kein Skill liest oder schreibt
Kanzleisoftware direkt — Anbindung läuft ausschließlich über Adapter/MCP-Sync
nach `kontext/` (siehe [`core/adapters/filesystem/README.md`](../adapters/filesystem/README.md)).

## Ordner-Format

```
kontext/
  kanzlei.md          Kanzlei-Profil (Pflicht)
  kontakte.md          Kontaktliste (empfohlen)
  mandate/
    2026-001.md         ein File je Mandat (Az. als Dateiname empfohlen)
    2026-002.md
  posteingang/          optional — unstrukturierte Eingänge (Rohdokumente)
  export/               optional — ausgehende Schreiben/Exporte
```

Beispiel (fiktive Daten, klar markiert): [`beispiel-kontext/`](beispiel-kontext/).

## `kanzlei.md` — Kanzlei-Profil

Freitext-Markdown mit mindestens einer `# `-Überschrift (Kanzleiname). Kein
striktes Frontmatter-Schema — Inhalt (Anschrift, Rechtsform,
Datenschutz-Verantwortlicher) liegt in der Konvention der Kanzlei. Der
Validator prüft nur Existenz + H1 (Warnung, kein Fehler, falls die
Überschrift fehlt).

## `kontakte.md` — Kontaktliste

Freitext-Markdown (Tabelle empfohlen: Name, Rolle, Kanal, Hinweis). Empfohlen,
nicht Pflicht — fehlt die Datei, meldet der Validator eine Warnung.

## `mandate/<az>.md` — Mandats-Schema (REICH)

Ein File je Mandat. Dateiname frei wählbar, empfohlen: das Aktenzeichen
(z. B. `2026-001.md`).

### Frontmatter

```yaml
---
az: "2026-001"            # Pflicht — Aktenzeichen, nicht leer
mandant: "Beispiel GmbH"   # Pflicht
gegenseite: "Muster AG"     # optional, String oder null
stand: 2026-07-01           # Pflicht — ISO-Datum (JJJJ-MM-TT), Stand dieser Datei
mandatsende: null            # Datum (ISO) oder null — speist Retention (P3)
streitwert: 12500.00          # Zahl oder null
status: aktiv                  # aktiv | ruhend | beendet
---
```

| Feld | Pflicht | Wert | Bedeutung |
|---|---|---|---|
| `az` | ja | String, nicht leer | Aktenzeichen. |
| `mandant` | ja | String, nicht leer | Mandant. |
| `gegenseite` | nein | String / `null` | Gegenseite, falls vorhanden. |
| `stand` | ja | ISO-Datum | Stand dieser Datei (nicht des Mandats). |
| `mandatsende` | empfohlen¹ | ISO-Datum / `null` | Speist einen Retention-Hinweis-Report (§ 66 StBerG, Handaktenfrist) — Executor noch nicht Teil dieses Snapshots, geplant. `null` = noch nicht beendet. |
| `streitwert` | empfohlen¹ | Zahl / `null` | Betrag in EUR, ohne Währungszeichen. |
| `status` | empfohlen¹ | `aktiv` / `ruhend` / `beendet` | Enum — ungültiger Wert ist ein Schema-Fehler, fehlender Schlüssel nur eine Warnung. |

¹ **Empfohlen, nicht Pflicht**: Fehlt der Schlüssel ganz, meldet der Validator
eine Warnung (kein Fehler) — die Rechenkette, die davon abhängt
(Retention-Executor), kann das Mandat dann nur als „nicht bewertbar"
ausweisen, ohne den restlichen Lauf zu blockieren.

### Markdown-Abschnitte (alle Pflicht)

- **`## Parteien`** — Tabelle `Rolle | Name | Vertreter`.
- **`## Kommunikation`** — **Verweis-Liste**, keine Volltext-Duplizierung
  (PII-Minimierung): `Datum — Betreff — [Datei](relativer-Link)`. Der Link
  zeigt auf `posteingang/` oder `export/`, nicht auf einen woanders
  liegenden Volltext.
- **`## Letzter Schritt`** — Freitext, ein bis wenige Sätze.
- **`## Nächste Frist`** — **Verweis auf die iCal-UID** aus dem
  Fristen-Export von `fristenrechner`
  (Format `<hash>@fristenrechner.legal-ops`), **keine Neuberechnung** (P3 —
  Fristen werden ausschließlich vom `fristenrechner`-Executor berechnet). Ist
  keine Frist offen, genügt ein expliziter Hinweis („Keine offene Frist").

### Validierung

CLI: [`validator.py`](validator.py) — reine Wenn-dann-Logik in
[`schema.py`](schema.py) (P3, Deterministik-Grenze: Claude liest nur den
Report, entscheidet nie selbst über Schema-Konformität).

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/core/context/validator.py --kontext <kontext-verzeichnis>
python3 ${CLAUDE_PLUGIN_ROOT}/core/context/validator.py --datei <mandat.md>
```

| Code | Bedeutung |
|---|---|
| `0` | Sauber — keine Schema-Fehler (Warnungen sind möglich und blockieren nicht). |
| `1` | Mindestens ein Schema-Fehler (Pflichtfeld, Datumsformat, Enum, fehlender Abschnitt). |
| `2` | Eingabefehler — Ziel (`--kontext`-Verzeichnis / `--datei`) existiert nicht. |

Ausgabe: JSON-Report (`quelle: "executor"`, P3) mit `fehler[]` und
`warnungen[]`, je Eintrag `datei:zeile: Meldung` wo ein Zeilenbezug existiert.
Verweis-Integrität (Markdown-Links in `## Kommunikation`) ist **immer nur
Warnung** — ein Ziel kann bewusst außerhalb des geprüften Verzeichnisses
liegen (z. B. e-Akte-Verweis).

## Struktur-Lint-Anbindung (`kontext_reads` / `kontext_writes`)

Skills, die `kontext/` lesen oder schreiben, deklarieren das optional im
SKILL.md-Frontmatter (vom [Struktur-Lint](../verify/struktur_lint.py) geprüft,
siehe dort und [CONVENTIONS.md](https://github.com/eliasreiche/tax-ops-germany/blob/main/CONVENTIONS.md)):

```yaml
kontext_reads:
  - mandate/*.md
  - kontakte.md
kontext_writes:
  - mandate/*.md
```

Muster müssen mit einem dokumentierten Bereich beginnen: `kanzlei.md`,
`mandate/`, `kontakte.md`, `posteingang/`, `export/`.

## Retention (Löschkonzept) — kein Auto-Delete (geplant)

`mandatsende` ist für einen Retention-Hinweis-Report vorgesehen (§ 66 StBerG,
Handaktenfrist) — Executor **löscht nie**, sondern markiert nur, was ab wann
löschbar wäre. Der Executor selbst ist (noch) nicht Teil dieses Snapshots aus
`legal-ops-germany` (siehe [`../VENDORED.md`](../VENDORED.md)).

## Bewusste Grenzen

- **Kein Volltext-Speicher** — `kontext/` ist ein schlanker Index/Verweis-
  Layer, keine Aktenverwaltung. Volltexte bleiben in der Kanzleisoftware bzw.
  in `posteingang/`/`export/` als Rohdokument, nie dupliziert im
  Mandats-File.
- **`kanzlei.md`/`kontakte.md` bewusst formfrei** — nur die Mandats-Datei hat
  ein striktes Frontmatter-Schema; die anderen beiden sind Freitext, weil ihr
  Inhalt kanzleispezifisch variiert und keine Rechenkette darauf aufbaut.
- **Verweis-Integrität ist Warnung, nicht Fehler** — der Validator prüft nur
  strukturelle Konformität, keine inhaltliche Richtigkeit der Verweise.
