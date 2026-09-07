# Schema — ao-fristenrechner

Datei-Kontrakt (P2) für den Executor
[`core/calc/ao_fristen/executor.py`](../../../core/calc/ao_fristen/executor.py).
Kein Netzwerkzugriff, keine Datenbank — JSON-Datei rein, JSON-Report raus.
Jede Anfrage trägt das Pflichtfeld `modus`.

## Modus `einspruch`

```json
{
  "modus": "einspruch",
  "bundesland": "BY",
  "aufgabe_zur_post_datum": "2026-02-03"
}
```

oder mit direktem Bekanntgabedatum:

```json
{
  "modus": "einspruch",
  "bundesland": "NW",
  "bekanntgabe_datum": "2026-01-15"
}
```

| Feld | Pflicht | Werte | Bedeutung |
|---|---|---|---|
| `bundesland` | ja | `BW BY BE BB HB HH HE MV NI NW RP SL SN ST SH TH` | Ort der Bekanntgabe (§ 108 Abs. 3 AO). |
| `bekanntgabe_datum` | entweder dies … | ISO-Datum | Bekanntgabe des Verwaltungsakts, direkt. |
| `aufgabe_zur_post_datum` | … oder dies | ISO-Datum, `>= 2025-01-01` | Aufgabe zur Post; Bekanntgabe wird über die Viertagesfiktion (§ 122 Abs. 2 Nr. 1 AO) berechnet. Vor 2025-01-01: Exit 1 (nicht abgedeckt). |
| `jahresfrist` | nein | `true`/`false` (Default `false`) | `true` = § 356 Abs. 2 AO (ein Jahr, fehlende/fehlerhafte Rechtsbehelfsbelehrung) statt § 355 Abs. 1 AO (ein Monat). |
| `fiktion_verschieben` | nein | `true`/`false` (Default `false`) | Ob der Bekanntgabe-Fiktionstag selbst nach § 108 Abs. 3 AO verschoben wird (nur bei `aufgabe_zur_post_datum`) — Default `false`, weil im Dossier `[unverifiziert]` (siehe SKILL.md „Nicht abgedeckt"). |

## Modus `abgabefrist`

```json
{
  "modus": "abgabefrist",
  "veranlagungszeitraum": 2024,
  "gruppe": "beraten",
  "bundesland": "NW"
}
```

| Feld | Pflicht | Werte | Bedeutung |
|---|---|---|---|
| `veranlagungszeitraum` | ja | ganze Jahreszahl `>= 2020` | Steuerjahr. |
| `gruppe` | ja | `nicht_beraten` \| `beraten` \| `land_forstwirt` | Fallgruppe nach § 149 Abs. 2/3 AO. `land_forstwirt` nur für VZ 2020–2024 hinterlegt (EGAO-Tabelle); ab VZ 2025 Exit 1 (nicht abgedeckt). |
| `bundesland` | ja | wie oben | Für die § 108 Abs. 3 AO-Verschiebung des (VZ-abhängigen) Nenndatums. |

Für VZ 2020–2024 liefert
[`abgabefristen.json`](../../../core/calc/ao_fristen/abgabefristen.json) die
Nenndaten aus Art. 97 § 36 Abs. 3 EGAO; ab VZ 2025 rechnet der Executor die
Regelfrist direkt aus § 149 Abs. 2 Satz 1 AO (`nicht_beraten`, 7 Monate nach
Jahresende) bzw. § 149 Abs. 3 AO (`beraten`, letzter Tag Februar zwei Jahre
später).

## Modus `vorauszahlung`

```json
{
  "modus": "vorauszahlung",
  "jahr": 2026,
  "steuerart": "ustva",
  "bundesland": "NW",
  "rhythmus": "monatlich",
  "dauerfristverlaengerung": true
}
```

| Feld | Pflicht | Werte | Bedeutung |
|---|---|---|---|
| `jahr` | ja | ganze Jahreszahl | Kalenderjahr der Termine. |
| `steuerart` | ja | `est` \| `kst` \| `gewst` \| `ustva` \| `lst` \| `zm` \| `sv` | Siehe [`vorauszahlungstermine.json`](../../../core/calc/ao_fristen/vorauszahlungstermine.json) für Normen/Quellen. |
| `bundesland` | ja | wie oben | Für § 108 Abs. 3 AO (Ausnahme: `sv`, siehe unten). |
| `rhythmus` | nur bei `ustva`/`lst` | `ustva`: `monatlich`/`quartalsweise`; `lst`: `monatlich`/`vierteljaehrlich`/`jaehrlich` | Meldezeitraum — wird als Kanzleiwissen verlangt, nicht aus einer Steuerhöhe hergeleitet (§ 18 Abs. 2 UStG / § 41a Abs. 2 EStG, bewusste Vereinfachung). |
| `dauerfristverlaengerung` | nein, nur `ustva` | `true`/`false` (Default `false`) | § 46 UStDV: verschiebt jeden Termin um einen Monat. |

`est`/`kst`/`gewst` haben feste Kalendertermine im Jahr (4 je Steuerart).
`zm` ist immer monatlich (25 Tage nach Monatsende). `sv` liefert 12 Termine
(drittletzter Bankarbeitstag) **ohne** § 108 Abs. 3 AO-Verschiebung
(eigenständiger Begriff, Dossier Abschnitt 8) — „Bankarbeitstag" ist hier
als Werktag ohne bundesweiten gesetzlichen Feiertag verstanden (bewusste
Annahme, nicht wörtlich im Dossier).

Jeder Termin trägt zusätzlich `schonfrist_ende` (Fälligkeit + 3 Tage,
§ 240 Abs. 3 Satz 1 AO) — informativ, gilt nicht bei Bar-/Scheckzahlung
(§ 240 Abs. 3 Satz 2 i. V. m. § 224 Abs. 2 Nr. 1 AO, siehe `hinweise`).

## Modus `verspaetungszuschlag`

```json
{
  "modus": "verspaetungszuschlag",
  "festgesetzte_steuer": 1000,
  "anzurechnende_betraege": 0,
  "abgabedatum": "2026-10-15",
  "fristende": "2026-07-31"
}
```

| Feld | Pflicht | Werte | Bedeutung |
|---|---|---|---|
| `festgesetzte_steuer` | ja | Zahl `>= 0` | Basis der Bemessungsgrundlage. |
| `anzurechnende_betraege` | nein (Default 0) | Zahl `>= 0` | Vorauszahlungen/anzurechnende Steuerabzugsbeträge. |
| `abgabedatum` | ja | ISO-Datum | Tatsächliches Abgabedatum der Steuererklärung. |
| `fristende` | ja | ISO-Datum | Fristende der Abgabefrist (z. B. aus Modus `abgabefrist` übernommen). |

Rechnet mit `Decimal` (kein Float). Bemessungsgrundlage und Monatsbetrag
werden auf volle Euro abgerundet (bewusste Annahme, siehe SKILL.md „Nicht
abgedeckt" — das Dossier zitiert § 152 Abs. 5 Satz 2 AO gekürzt). Ausgabe:
`angefangene_monate`, `zuschlag_pro_monat` (mind. 25 €), `zuschlag_gesamt`
(gedeckelt auf 25.000 €, § 152 Abs. 10 AO), `hoechstbetrag_erreicht`. Der
Pflicht-/Ermessensfall (§ 152 Abs. 1/2 AO) erscheint nur als `hinweise`-Text,
ungewertet (siehe SKILL.md).

## Ausgabe: JSON-Report

Jeder Modus liefert `meta`, `rechenkette` (`RechenSchritt`-Liste,
`quelle: "executor"`), modusspezifische Felder, `warnungen`/`hinweise` sowie
`kalender_termine` — eine normierte Liste `[{datum, titel, norm}, …]` für den
Kalender-Export (ein bis zwölf Einträge je nach Modus). Vollständige
Beispiele:
[`beispiel-report-einspruch.json`](beispiel-report-einspruch.json),
[`beispiel-report-abgabefrist.json`](beispiel-report-abgabefrist.json),
[`beispiel-report-vorauszahlung.json`](beispiel-report-vorauszahlung.json),
[`beispiel-report-verspaetungszuschlag.json`](beispiel-report-verspaetungszuschlag.json).

## Kalender-Export (zweite Stufe: calc → export)

```
python3 ${CLAUDE_PLUGIN_ROOT}/core/calc/ao_fristen/kalender_executor.py \
  --report REPORT.json --format ics|csv|beide \
  [--output DATEI | --output-dir ORDNER] \
  [--aktenzeichen AZ] [--vorlauftage N]
```

**Eingabe ist ausschließlich der Report oben** — kein zweiter Fachdatensatz,
keine erneute Rechnung; der Report muss `quelle == "executor"` tragen.
Beispiele: [`beispiel-export.ics`](beispiel-export.ics),
[`beispiel-export.csv`](beispiel-export.csv).

| Flag | Pflicht | Bedeutung |
|---|---|---|
| `--report` | ja | JSON-Report aus `executor.py`. |
| `--format` | nein | `ics` (Default), `csv` oder `beide` (verlangt `--output-dir`). |
| `--output` / `--output-dir` | nein | Zieldatei bzw. -ordner (Dateiname `ao-frist-<id8>.ics/.csv`); ohne beides: stdout. |
| `--aktenzeichen` | nein | Az als Label (kein Rechenwert), fließt in Titel, CSV und UID-Identität ein. |
| `--vorlauftage` | nein | Vorfrist-Vorlauf in Tagen (Default 3). |

**„Re-Export nur bei Korrektur" (P3).** Die VEVENT-`UID` je Termin ist ein
Hash aus Modus, den normierten Eingabewerten des Reports, dem Termin-Datum
und dem Aktenzeichen. Unveränderte Eingabe → byte-identischer Export →
Re-Import aktualisiert dasselbe Ereignis (kein Duplikat, zweimal exportieren
ergibt identische Dateien). Eine Korrektur ändert die Identität → neue `UID`.

**iCal (`.ics`, RFC 5545).** Ein Ganztags-`VEVENT` je Eintrag in
`kalender_termine`, mit `VALARM`-Vorfrist, Norm-Angabe (✅-markiert) und der
Zweitkontroll-Klausel in der `DESCRIPTION`.

**CSV (`;`-getrennt).** Eine Zeile je Termin, Kopf: `datum;vorfrist;
vorlauftage;titel;norm;modus;aktenzeichen;uid;quelle`.

Exit-Codes: `0` = Export erzeugt, `2` = Eingabefehler (Report-Datei fehlt,
ungültiges JSON, kein gültiger Executor-Report, Schreibfehler; kein
Traceback) — folgt der allgemeinen Executor-Konvention in
[CONVENTIONS.md](https://github.com/eliasreiche/tax-ops-germany/blob/main/CONVENTIONS.md).

## Exit-Codes des `executor.py`

`0` = Report erzeugt · `1` = fachlicher Fehler/Schema-Verstoß (fehlendes
Pflichtfeld, falscher Typ, unbekanntes Bundesland/Steuerart/Modus, sowie
die Eingabe bräuchte eine im Quellen-Dossier nicht belegte Regel — siehe
SKILL.md „Nicht abgedeckt") · `2` = Eingabefehler (Eingabedatei fehlt,
ungültiges JSON) — folgt der allgemeinen Executor-Konvention in
[CONVENTIONS.md](https://github.com/eliasreiche/tax-ops-germany/blob/main/CONVENTIONS.md).
