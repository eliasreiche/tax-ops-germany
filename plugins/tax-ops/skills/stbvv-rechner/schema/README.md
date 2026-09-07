# Schema — stbvv-rechner

Datei-Kontrakt (P2) für den Executor
[`core/calc/stbvv/executor.py`](../../../core/calc/stbvv/executor.py).
Kein Netzwerkzugriff, keine Datenbank — JSON-Datei rein, JSON-Report raus.

## Eingabe: StBVV-Anfrage (JSON, `--input`)

Genau **ein** Hauptberechnungs-Block je Anfrage — `wertgebuehr`,
`zeitgebuehr` oder `betragsrahmen`:

```json
{
  "wertgebuehr": { "...": "siehe unten" },
  "auslagenpauschale": true,
  "umsatzsteuer": true
}
```

### Block `wertgebuehr` (§§ 21, 24, 33, 35 StBVV)

```json
{
  "tatbestand_id": "24-1-nr1-est-erklaerung",
  "gegenstandswert": "50000.00",
  "referenzpunkt": "mittelgebuehr"
}
```

- `tatbestand_id`: Pflicht, eine Id aus
  [`katalog.json`](../../../core/calc/stbvv/katalog.json).
- `gegenstandswert`: Pflicht, Dezimalstring (> 0). Liegt der Wert unter dem
  in `katalog.json` hinterlegten Mindestwert der Tätigkeit, hebt der
  Executor ihn sichtbar (eigene Rechenschritt-Zeile) auf den Mindestwert an.
- **entweder** `satz` (expliziter Zehntelsatz als Dezimalstring, z. B.
  `"0.35"`, muss im Rahmen `satz_min`-`satz_max` des Katalogeintrags liegen)
  **oder** `referenzpunkt` (`"untergrenze"` / `"mittelgebuehr"` /
  `"obergrenze"`) — nicht beides, nicht keines (§ 11 StBVV verlangt eine
  bewusste Ermessensentscheidung, keine automatische Annahme).
- optional `erstberatung_verbraucher: true` — nur für die Id
  `21-1-rat-auskunft` zulässig (§ 21 Abs. 1 Satz 2 StBVV: Kappung auf
  190 Euro bei Erstberatung eines Verbrauchers); bei jeder anderen Id ein
  Eingabefehler.

### Block `zeitgebuehr` (§ 13 StBVV)

```json
{
  "stichtag": "2025-09-01",
  "minuten": 100,
  "referenzpunkt": "obergrenze"
}
```

- `stichtag`: Pflicht, ISO-Datum. Muss `>= 2025-07-01` sein (aktuelle
  Fassung) — ein früherer Stichtag ist eine Lücke (Exit 2).
- `minuten`: Pflicht, ganze Zahl >= 1. Wird auf angefangene Viertelstunden
  aufgerundet (14 Min. -> 1 Einheit, 15 Min. -> 1 Einheit, 16 Min. ->
  2 Einheiten).
- `satz`/`referenzpunkt`: wie oben, Rahmen 16,50-41,00 Euro je Einheit.

### Block `betragsrahmen` (§ 34 StBVV, Lohnbuchführung)

```json
{
  "tatbestand_id": "34-2-lohnabrechnung",
  "einheiten": 5,
  "referenzpunkt": "mittelgebuehr"
}
```

- `tatbestand_id`: Pflicht, eine `art: "betragsrahmen_je_einheit"`-Id aus
  `katalog.json` (§ 34 Abs. 1-4 StBVV).
- `einheiten`: Pflicht, ganze Zahl >= 1 (z. B. Anzahl Arbeitnehmer).
- `satz_je_einheit`/`referenzpunkt`: wie oben, Rahmen aus dem Katalogeintrag.

### Auslagenpauschale und Umsatzsteuer (top-level, für jeden Block)

- `auslagenpauschale` (Boolean, Default `true`): § 16 StBVV — 20 % der
  Gebühr, höchstens 20 Euro.
- `umsatzsteuer` (Boolean, Default `true`) und optional `umsatzsteuersatz`
  (Dezimalstring, Default `"0.19"`): § 15 StBVV.

Jeder nicht vorgesehene Key auf oberster Ebene oder innerhalb eines Blocks
ist ein Eingabefehler (Exit 2, mit Namen des Keys) — kein stilles Ignorieren.

Geldbeträge und Sätze **immer als JSON-String**, nie als `float` — der
Executor lehnt `float`-Eingaben strikt ab.

## Ausgabe: Report (JSON, `--output` oder stdout)

```json
{
  "meta": { "erzeugt_von": "...", "quelle_datei": "...", "deterministik": "..." },
  "berechnung": { "art": "wertgebuehr", "bezeichnung": "...", "norm": "...", "details": { "...": "..." } },
  "rechenkette": [ { "schritt": 1, "norm": "...", "beschreibung": "...", "ergebnis": "...", "quelle": "executor" } ],
  "ergebnis": {
    "gebuehr": "456.40",
    "auslagenpauschale": "20.00",
    "netto": "476.40",
    "umsatzsteuersatz": "0.19",
    "umsatzsteuer": "90.52",
    "brutto": "566.92",
    "quelle": "executor"
  }
}
```

`ergebnis.auslagenpauschale`/`umsatzsteuersatz`/`umsatzsteuer` sind `null`,
wenn die jeweilige Anfrage-Flag auf `false` stand. Jeder Geldbetrag stammt
aus `core/calc/stbvv/rechner.py`, nie vom Modell (P3).

## Beispiele

- [`beispiel-eingabe-wertgebuehr.json`](beispiel-eingabe-wertgebuehr.json) /
  [`beispiel-report.json`](beispiel-report.json) — ESt-Erklärung,
  Mittelgebühr.
- [`beispiel-eingabe-zeitgebuehr.json`](beispiel-eingabe-zeitgebuehr.json) —
  100 Minuten, Obergrenze.
- [`beispiel-eingabe-betragsrahmen.json`](beispiel-eingabe-betragsrahmen.json)
  — Lohnabrechnung für 5 Arbeitnehmer, Mittelgebühr.
