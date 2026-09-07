---
name: stbvv-rechner
description: "Berechnet StBVV-Gebühren (Wertgebühr, Zeitgebühr, Betragsrahmen je Einheit) deterministisch mit nachvollziehbarer Rechenkette — Wertstufen-Tabellen A-C, Zehntelrahmen, Zeitgebühr ab 01.07.2025, Auslagenpauschale, USt. Triggert bei StBVV berechnen, Steuerberatergebühr, Honorar/Vergütung Steuerberater, Gegenstandswert zu Gebühr, Kostennote Steuerberater."
status: beta
welle: 6
bereich: verguetung
stberg_einordnung: "Rechnen nach Tabelle/Gesetz ohne Subsumtion: der Rechner sucht die volle Gebühr nach Wertstufe und multipliziert mit einem vom Steuerberater gewählten Satz — die Einordnung der Tätigkeit unter einen Katalogtatbestand und die Wahl des Zehntelsatzes im Rahmen (§ 11 StBVV: Ermessen nach Umfang, Schwierigkeit, Bedeutung, Einkommens-/Vermögensverhältnissen, Haftungsrisiko) bleiben beim Berufsträger."
daten_hinweis: "Benötigt nur Gegenstandswert/Minuten/Einheiten und eine Tatbestands-Id — keine Mandantendaten erforderlich. Der Executor arbeitet rein lokal, ohne Netzwerkzugriff."
haftung: "Zweitkontrolle, zwingend: Der Rechner ersetzt keine Prüfung der Kostenrechnung durch den Steuerberater. Die Angemessenheit des gewählten Satzes nach § 11 StBVV wird nicht geprüft — das bleibt Ermessensentscheidung des Berufsträgers. Jeder Betrag ist vor Rechnungsstellung gegenzuprüfen, insbesondere Gegenstandswert-Ermittlung, Zehntelsatz-Wahl und Tabellenstand."
---

# stbvv-rechner

> **Status: `beta`** — automatisierte Tests laufen grün in CI (`tests/`).
> Noch **nicht** händisch abgenommen — `status: getestet` vergibt erst der
> Maintainer nach eigener Prüfung (siehe
> [CONVENTIONS.md](https://github.com/eliasreiche/tax-ops-germany/blob/main/CONVENTIONS.md),
> Reifegrad-Leiter).

## Zweck

Berechnet StBVV-Gebühren deterministisch über den Executor
[`core/calc/stbvv/`](../../core/calc/stbvv/) — mit vollständiger,
nachvollziehbarer **Rechenkette**: Wertstufen-Suche in der einschlägigen
Tabelle (A-C), volle Gebühr (10/10) × Zehntelsatz im gesetzlichen Rahmen,
Zeitgebühr (angefangene Viertelstunden × Satz), Betragsrahmen je Einheit
(Lohnbuchführung, § 34 StBVV), Auslagenpauschale (§ 16 StBVV) und
Umsatzsteuer (§ 15 StBVV).

**Positionierung: strikt Zweitkontrolle.** Das Modell rechnet nie selbst —
kein Kopfrechnen, kein Schätzen von Sätzen. Jeder Geldbetrag in der Antwort
stammt unverändert aus dem Executor-Report. Der Rechner trifft keine
Ermessensentscheidung nach § 11 StBVV — der Satz im Zehntel-/Betragsrahmen
ist entweder ein expliziter Wert des Steuerberaters oder einer der
Referenzpunkte `untergrenze`/`mittelgebuehr`/`obergrenze`; eine fehlende
Angabe ist ein Eingabefehler, nie eine automatische Annahme.

**Ein Berechnungsblock je Anfrage (v1, KISS):** `wertgebuehr`,
`zeitgebuehr` oder `betragsrahmen` — genau einer. Mehrere Tätigkeiten in
einer Kostennote ruft Claude als mehrere Executor-Aufrufe auf und summiert
selbst; der Executor kennt keine Angelegenheits-Gruppierung.

## Eingaben (Datei-Kontrakt, P2)

| Eingabe | Pflicht | Format | Beschreibung |
|---|---|---|---|
| StBVV-Anfrage | ja | `.json` | genau ein Block `wertgebuehr`, `zeitgebuehr` oder `betragsrahmen`, siehe [`schema/README.md`](schema/README.md) und die Beispiele darin. |

Kurzfassung:

- **`wertgebuehr`**: `tatbestand_id` (aus [`katalog.json`](../../core/calc/stbvv/katalog.json):
  §§ 21, 24, 33, 35 StBVV), `gegenstandswert` (Dezimalstring), dazu
  **entweder** `satz` (expliziter Zehntelsatz im Rahmen) **oder**
  `referenzpunkt` (`untergrenze`/`mittelgebuehr`/`obergrenze`) — nicht
  beides. Optional `erstberatung_verbraucher: true` (nur für
  `21-1-rat-auskunft`: Kappung auf 190 Euro, § 21 Abs. 1 Satz 2 StBVV).
- **`zeitgebuehr`**: `stichtag` (ISO-Datum, ab `2025-07-01` — ältere
  Stichtage sind eine Lücke, kein primärquellig geprüfter Altsatz),
  `minuten` (ganze Zahl), dazu `satz` oder `referenzpunkt` (Rahmen
  16,50-41 Euro je angefangene Viertelstunde, § 13 StBVV).
- **`betragsrahmen`**: `tatbestand_id` (§ 34 StBVV, Lohnbuchführung),
  `einheiten` (ganze Zahl, z. B. Anzahl Arbeitnehmer), dazu
  `satz_je_einheit` oder `referenzpunkt`.
- **`auslagenpauschale`** (Default `true`): § 16 StBVV, 20 % der Gebühr,
  höchstens 20 Euro.
- **`umsatzsteuer`** (Default `true`) und optional `umsatzsteuersatz`
  (Dezimalstring, Default `"0.19"`): § 15 StBVV.

Ein nicht vorgesehener Key (Tippfehler) führt zu Exit 2 mit Nennung des
Keys — nie stilles Ignorieren. Geldbeträge und Sätze immer als
JSON-**String** (z. B. `"5000.00"`), nie als `float` (Rundungsfehler wie
0,1+0,2 sind bei Geldbeträgen ein Haftungsrisiko).

## Ablauf

1. **Claude schreibt die Anfrage als JSON-Datei** (nach
   [`schema/README.md`](schema/README.md)). Fehlende Pflichtangaben
   (Gegenstandswert, Tatbestands-Id, Satz/Referenzpunkt) werden beim
   Nutzer erfragt, nie ergänzt oder geschätzt.
2. **Claude ruft den Executor auf**:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/core/calc/stbvv/executor.py \
     --input <anfrage.json> \
     --output <report.json>
   ```

3. **Der Executor entscheidet jeden Betrag deterministisch** (P3). Claude
   liest ausschließlich den JSON-Report und übernimmt volle Gebühr, Satz,
   Zwischenbetrag, Auslagenpauschale, USt und Bruttobetrag unverändert.
4. **Claude stellt den Report als Rechenkette dar**: jeder Schritt mit Norm
   und Zwischenergebnis. Dabei immer ausweisen:
   - **welche Tabelle/Wertstufe** angewendet wurde (bzw. die
     Fortschreibungsformel oberhalb der letzten Stufe),
   - **Mindestgegenstandswert**, wenn er gegriffen hat
     (`mindestwert_gegriffen`),
   - **den gewählten Satz** und die drei Referenzpunkte (Untergrenze/
     Mittelgebühr/Obergrenze) zur Einordnung,
   - **Erstberatungs-Kappung** (190 Euro), wenn angefordert und gegriffen,
   - **Netto/Brutto** mit Auslagenpauschale und USt getrennt ausgewiesen,
   - den Zweitkontroll-Hinweis aus `haftung` (immer, bei jeder Antwort).
5. Bei Exit-Code 2 (Eingabefehler, u. a. unbekannte Tatbestands-Id,
   Gegenstandswert außerhalb einer hinterlegten Tabelle ohne
   Fortschreibungsformel, Zeitgebühr-Stichtag vor 2025-07-01, Satz
   außerhalb des Rahmens, unbekannter Key) gibt Claude die Fehlermeldung
   wieder und korrigiert die Eingabe bzw. fragt nach — er rät kein
   Ergebnis.

## Output-Format

JSON-Report nach [`schema/README.md`](schema/README.md), Beispiel:
[`schema/beispiel-report.json`](schema/beispiel-report.json). Kernfelder:
`berechnung` (Art, Bezeichnung, Norm, Details), `rechenkette`, `ergebnis`
(`gebuehr`, `auslagenpauschale`, `netto`, `umsatzsteuer`, `brutto`, je
`quelle: "executor"`).

## Beispiele

### Beispiel 1 — Wertgebühr: Einkommensteuererklärung, Mittelgebühr

Gegenstandswert 50.000 Euro (Summe der positiven Einkünfte), § 24 Abs. 1
Nr. 1 StBVV, Zehntelrahmen 1/10-6/10, Mittelgebühr:

| Schritt | Norm | Ergebnis |
|---|---|---|
| Volle Gebühr (Tabelle A, Wertstufe bis 50.000 Euro) | Anlage 1 StBVV | 1.304,00 € |
| Zehntelrahmen 1/10-6/10, Mittelgebühr | § 24 Abs. 1 Nr. 1 StBVV | Satz 0,35 |
| Gebühr: 0,35 × 1.304,00 € | Hausregel (Rundung) | 456,40 € |
| Auslagenpauschale (20 %, gedeckelt) | § 16 StBVV | 20,00 € |
| Netto | | 476,40 € |
| USt (19 %) | § 15 StBVV | 90,52 € |
| **Brutto** | | **566,92 €** |

### Beispiel 2 — Zeitgebühr: 100 Minuten, Obergrenze

Stichtag 01.09.2025 (nach dem 01.07.2025, aktuelle Fassung), 100 Minuten,
Obergrenze 41,00 Euro je angefangene Viertelstunde:

| Schritt | Norm | Ergebnis |
|---|---|---|
| 100 Minuten -> angefangene Viertelstunden | § 13 StBVV | 7 |
| Satz (Obergrenze) | § 13 StBVV | 41,00 € |
| Gebühr: 41,00 € × 7 | Hausregel (Rundung) | 287,00 € |
| **Netto/Brutto (ohne Auslagen/USt angefordert)** | | **287,00 €** |

### Beispiel 3 — Scope-Ablehnung: Zeitgebühr vor dem Stichtag

Anfrage mit `"stichtag": "2024-01-01"` liefert Exit 2: „Zeitgebühr § 13
StBVV: Stichtag 2024-01-01 liegt vor 2025-07-01 (aktuelle Fassung, BGBl.
2025 I Nr. 105) — für frühere Stichtage ist kein Satz primärquellig
geprüft, keine automatische Berechnung möglich." Claude gibt diese Meldung
wieder und schätzt keinen Altsatz.

## Quellenstand

- **StBVV-Text** (§§ 10, 11, 13, 15, 16, 21, 24, 33, 34, 35 sowie Anlagen
  1-4) über gesetze-im-internet.de, abgerufen am **2026-09-08**. Anlagen
  1-3 tragen die Fundstelle „BGBl. 2025 I Nr. 105" (Anlage 4: „BGBl. 2025
  Nr. 105" — so auf der Quellseite, ohne „I"), laut Primärquellen-Dossier
  (siehe unten, Abschnitt 9) in Kraft seit **2025-07-01**; das Inkrafttretensdatum wurde
  nur für § 13 StBVV primärquellig separat verifiziert (Dossier), nicht für
  jede Anlage einzeln — siehe `stand`-Feld je Tabelle in
  [`tabellen.json`](../../core/calc/stbvv/tabellen.json).
- **Primärquellen-Dossier**: `Steuer-Ops DE/dossier-ao-fristen-stbvv-2026-09-08.md`
  Abschnitt 9 (Vault, außerhalb dieses Repos) — nur die dort als „belegt"
  markierten Zeilen sind in den Rechner eingeflossen.
- **Katalog**: `katalog.json` enthält jede Zeile mit `quelle_url`
  (gesetze-im-internet.de, Einzelnorm).

## Nicht abgedeckt

- **§ 40 StBVV (Rechtsbehelfsverfahren u. a.)**: verweist auf das RVG
  ("sinngemäße Anwendung") und dessen eigene Wertgebührentabelle (Anlage 2
  RVG) — eine im StBVV-Text selbst als „Tabelle E" bezeichnete Tabelle
  existiert **nicht** (verifiziert: die StBVV kennt nur die Anlagen 1-4,
  Tabellen A-D). Eine RVG-Berechnung leistet der Skill `rvg-gkg-rechner`
  aus `legal-ops-germany` — hier nicht vendort (Scope-Grenze, KISS).
- **Tabelle D (Anlage 4, Land-/Forstwirtschaft, § 39 StBVV)**: Wertstufen
  vollständig in `tabellen.json` hinterlegt (Teil a: Betriebsfläche, 59
  Stufen; Teil b: Jahresumsatz, 85 Stufen), aber **kein Katalogeintrag** —
  § 39 StBVV ist nicht Teil dieses Skill-Scopes. Teil a hat oberhalb der
  letzten Stufe (1.000 ha) zudem ein abweichendes Fortschreibungsschema
  (gestaffelter Betrag je vollem Hektar statt „je angefangene X Euro") —
  nicht implementiert, der Rechner lehnt eine Anfrage in diesem Bereich ab.
- **§ 22 (Gutachten/verbindliche Auskunft), § 23 (sonstige
  Einzeltätigkeiten), §§ 25-27, 30, 37 StBVV**: nicht im Katalog — diese
  Normen wurden für v1 nicht primärquellig aufgearbeitet.
- **Pauschalvergütung (§ 4 StBVV)**: Vereinbarungssache zwischen
  Steuerberater und Auftraggeber, kein gesetzlicher Rahmen — kein
  Rechenfall für diesen Skill.
- **Vergütungsvereinbarung (§ 4a, § 4b StBVV)**: individuelle Vereinbarung,
  nicht rechenbar.
- **Zeitgebühr vor dem 01.07.2025**: kein primärquellig geprüfter Altsatz
  hinterlegt — der Executor lehnt einen früheren Stichtag ab.
- **Mehrere Tätigkeiten/Angelegenheiten in einer Anfrage**: v1 rechnet
  genau einen Block je Aufruf (siehe „Ein Berechnungsblock je Anfrage"
  oben) — keine automatische Summierung mehrerer Tatbestände oder
  Angelegenheits-Gruppierung wie beim RVG-Rechner.
