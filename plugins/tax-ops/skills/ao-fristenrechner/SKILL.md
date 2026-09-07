---
name: ao-fristenrechner
description: "Berechnet AO-Fristen deterministisch mit nachvollziehbarer Rechenkette: Einspruchsfrist (§ 355/§ 356 AO, inkl. Bekanntgabefiktion § 122 Abs. 2 Nr. 1 AO), Abgabefristen (§ 149 Abs. 2/3 AO, Art. 97 § 36 EGAO), Vorauszahlungs-/Anmeldetermine (ESt/KSt/GewSt/USt-VA/LSt/ZM/SV) und Verspätungszuschlag (§ 152 AO). Triggert bei AO-Fristberechnung, Einspruchsfrist, Abgabefrist, Steuererklärung Frist, Vorauszahlungstermin, Dauerfristverlängerung, Verspätungszuschlag. Strikt Zweitkontrolle, ersetzt keine Fristenkontrolle der Kanzlei."
status: beta
welle: 6
bereich: fristen
stberg_einordnung: "Rechnen nach Tabelle/Gesetz ohne Subsumtion: der Skill wendet §§ 108, 122, 149, 152, 240 AO und die Termine der Einzelsteuergesetze mechanisch an. Die Einordnung des fristauslösenden Ereignisses (wirksame Bekanntgabe, richtige Fristart, ob eine Rechtsbehelfsbelehrung tatsächlich fehlt/fehlerhaft ist, Pflicht- vs. Ermessensfall beim Verspätungszuschlag) bleibt beim Berufsträger."
daten_hinweis: "Die Berechnung benötigt nur Datum/Jahr, Fristart bzw. Steuerart, Bundesland und ggf. Steuerbeträge — keine Mandantennamen. Wird beim Kalender-Export ein Aktenzeichen mitgegeben, kann die Export-Datei (.ics/.csv) dieses tragen — dann wie eine Akte behandeln. Beide Executors arbeiten rein lokal, ohne Netzwerkzugriff."
haftung: "Zweitkontrolle, zwingend: Der Rechner ist das zweite Augenpaar, nie das erste — er ersetzt keine Fristenkontrolle der Kanzlei (Fristenkalender, Vier-Augen-Prinzip, Endkontrolle durch den Berufsträger bleiben unberührt). Bei Notfristen (Einspruch) und bei allem, was im Dossier nicht vollständig belegt ist (siehe „Nicht abgedeckt"), gilt das doppelt. Der Kalender-Export ist ein technischer Übernahmehelfer; Import und Kontrolle im Zielsystem verantwortet die Kanzlei."
---

# ao-fristenrechner

> **Status: `beta`** — automatisierte Tests laufen grün in CI (`tests/`),
> noch keine händische Live-Abnahme durch den Maintainer. Keine
> Produktions-Garantie — Zweitkontrolle bleibt Pflicht (siehe
> [CONVENTIONS.md](https://github.com/eliasreiche/tax-ops-germany/blob/main/CONVENTIONS.md), Reifegrad-Leiter).

## Zweck

Berechnet vier AO-Fristarten deterministisch über den Executor
[`core/calc/ao_fristen/`](../../core/calc/ao_fristen/) — jede mit
vollständiger, nachvollziehbarer **Rechenkette** (Norm + Zwischenwert je
Schritt, `quelle: "executor"`):

1. **Einspruchsfrist** (§ 355 Abs. 1 AO, ein Monat; § 356 Abs. 2 AO bei
   fehlender/fehlerhafter Rechtsbehelfsbelehrung, ein Jahr) — aus einem
   Bekanntgabedatum oder aus dem Datum der Aufgabe zur Post über die
   Bekanntgabefiktion des § 122 Abs. 2 Nr. 1 AO (vier Tage, gültig seit
   01.01.2025).
2. **Abgabefrist** (§ 149 Abs. 2/3 AO) für einen Veranlagungszeitraum,
   beraten/nicht beraten, inkl. der verlängerten Fristen nach Art. 97 § 36
   EGAO für VZ 2020–2024.
3. **Vorauszahlungs- und Anmeldetermine** eines Kalenderjahres: ESt, KSt,
   GewSt, USt-Voranmeldung (mit Dauerfristverlängerung), LSt-Anmeldung,
   Zusammenfassende Meldung, SV-Beitragsfälligkeit.
4. **Verspätungszuschlag** (§ 152 Abs. 5, 10 AO) aus festgesetzter Steuer,
   anzurechnenden Beträgen, Abgabedatum und Fristende.

Jede Wochenend-/Feiertagsverschiebung läuft über § 108 Abs. 3 AO
(Feiertage aus [`core/calc/feiertage/`](../../core/calc/feiertage/), alle
16 Bundesländer) — mit derselben ehrlichen Kennzeichnung teilgebietlicher
Feiertage (BY, SN, TH) wie im Schwesterprojekt
[legal-ops-germany](https://github.com/eliasreiche/legal-ops-germany):
ändert ein teilgebietlicher Feiertag das Ergebnis möglicherweise, zeigt der
Report **beide** möglichen Daten mit Warnung, nie eines stillschweigend.

**Zwei Stufen: berechnen → exportieren.** Nach der Berechnung erzeugt der
Skill aus dem Report einen Kalender-/Docketing-Export (iCal `.ics` / CSV)
über [`core/calc/ao_fristen/kalender_executor.py`](../../core/calc/ao_fristen/kalender_executor.py)
— **idempotent**: dieselbe Eingabe ergibt denselben Export (kein Duplikat
beim Re-Import), erst eine Korrektur erzeugt eine neue `UID`.

**Positionierung: strikt Zweitkontrolle.** Der Rechner ersetzt keine
Fristenkontrolle der Kanzlei. **Deterministik-Grenze (P3):** Claude rechnet
nie selbst — kein Kopfrechnen, kein Datums-Schätzen. Jeder Wert in der
Antwort stammt unverändert aus dem Executor-Report.

## Eingaben (Datei-Kontrakt, P2)

Eine JSON-Anfrage mit Pflichtfeld `modus` (`einspruch` | `abgabefrist` |
`vorauszahlung` | `verspaetungszuschlag`). Vollständiges Schema und je Modus
ein Beispiel: [`schema/README.md`](schema/README.md).

| Modus | Pflichtfelder | Optional |
|---|---|---|
| `einspruch` | `bundesland`, genau eines von `bekanntgabe_datum` / `aufgabe_zur_post_datum` | `jahresfrist` (Default `false`), `fiktion_verschieben` (Default `false`) |
| `abgabefrist` | `veranlagungszeitraum`, `gruppe` (`nicht_beraten`/`beraten`/`land_forstwirt`), `bundesland` | — |
| `vorauszahlung` | `jahr`, `steuerart` (`est`/`kst`/`gewst`/`ustva`/`lst`/`zm`/`sv`), `bundesland` | `rhythmus` (bei `ustva`/`lst` Pflicht), `dauerfristverlaengerung` (nur `ustva`) |
| `verspaetungszuschlag` | `festgesetzte_steuer`, `abgabedatum`, `fristende` | `anzurechnende_betraege` (Default 0) |

Fehlende Pflichtangaben werden beim Nutzer erfragt, nie ergänzt oder
geraten (Anti-Halluzination). `bundesland` steht bei jeder wochenend-
/feiertagsabhängigen Berechnung, weil § 108 Abs. 3 AO auf den Ort der
Bekanntgabe/Fälligkeit abstellt — nennt der Nutzer keines, fragt Claude nach.

## Ablauf

1. **Claude schreibt die Anfrage als JSON-Datei** nach
   [`schema/README.md`](schema/README.md).
2. **Claude ruft den Executor auf** (kein eigenes Rechnen):

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/core/calc/ao_fristen/executor.py \
     --input <anfrage.json> --output <report.json>
   ```

3. **Bei Exit-Code 2 (nicht abgedeckt)** gibt Claude die Meldung wieder und
   erklärt, warum die Eingabe eine im Quellen-Dossier nicht belegte Regel
   bräuchte (siehe „Nicht abgedeckt" unten) — kein Ergebnis wird geraten.
   **Bei Exit-Code 1 (Eingabefehler)** fragt Claude nach der korrigierten
   Eingabe.
4. **Claude stellt den Report als Rechenkette dar**: jeder Schritt mit Norm
   und Zwischenergebnis, alle `warnungen` und `hinweise` sichtbar — bei
   Einspruchsfrist insbesondere die Notfrist-Eigenschaft (§ 355 AO ist eine
   gesetzliche Frist, kein Notfrist-Flag im Katalog, aber fristgebunden) und
   den `fiktion_verschieben`-Hinweis; bei teilgebietlichen Feiertagen beide
   möglichen Enden; bei Verspätungszuschlag den Pflicht-/Ermessens-Hinweis
   ungewertet. Immer: der Zweitkontroll-Hinweis aus `haftung`.
5. **Claude erzeugt den Kalender-Export** aus dem Report (kein erneutes
   Rechnen), ein Aktenzeichen nur, wenn der Nutzer es genannt hat:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/core/calc/ao_fristen/kalender_executor.py \
     --report <report.json> --format beide --output-dir <ordner> \
     [--aktenzeichen <az>] [--vorlauftage <n>]
   ```

6. **Kein neuer Export ohne Korrektur** — die `UID` ist stabil, solange die
   Eingabe unverändert bleibt (siehe „Kalender-Export" unten).

## Output-Format

JSON-Report nach [`schema/README.md`](schema/README.md), Beispiele je Modus:
[`schema/beispiel-report-einspruch.json`](schema/beispiel-report-einspruch.json),
[`schema/beispiel-report-abgabefrist.json`](schema/beispiel-report-abgabefrist.json),
[`schema/beispiel-report-vorauszahlung.json`](schema/beispiel-report-vorauszahlung.json),
[`schema/beispiel-report-verspaetungszuschlag.json`](schema/beispiel-report-verspaetungszuschlag.json).
Jeder Report trägt `rechenkette`, `kalender_termine` (normiert für den
Export) und `quelle: "executor"`.

**Kalender-Export**, Beispiele:
[`schema/beispiel-export.ics`](schema/beispiel-export.ics),
[`schema/beispiel-export.csv`](schema/beispiel-export.csv). Ein
Ganztags-`VEVENT`/eine CSV-Zeile je Eintrag in `kalender_termine`, mit
`VALARM`-Vorfrist, Norm-Kennzeichnung und Zweitkontroll-Klausel. Format-,
Feld- und UID-Details: [`schema/README.md`](schema/README.md) → „Kalender-Export".

## Beispiele

### Beispiel 1 — Einspruchsfrist, Fiktionstag auf Samstag

Aufgabe zur Post am 03.02.2026 (Dienstag), Bundesland BY,
`fiktion_verschieben` nicht gesetzt (Default `false`): der Fiktionstag
(+4 Tage) fällt auf Samstag, 07.02.2026.

| Schritt | Norm | Ergebnis |
|---|---|---|
| Aufgabe zur Post 03.02.2026 + 4 Tage | § 122 Abs. 2 Nr. 1 AO | 07.02.2026 (Sa) — Bekanntgabedatum, **nicht** verschoben (Default) |
| Bekanntgabetag zählt nicht mit | § 108 Abs. 1 AO i. V. m. § 187 Abs. 1 BGB | Fristbeginn 08.02.2026 |
| Monatsfrist | § 355 Abs. 1 AO, § 188 Abs. 2 BGB | 07.03.2026 (Sa) |
| Sa → So → nächster Werktag | § 108 Abs. 3 AO (zweimal) | **09.03.2026 (Mo)** |

Hinweis: mit `fiktion_verschieben: true` würde stattdessen schon der
Fiktionstag selbst auf den nächsten Werktag verschoben (07.02. Sa → 08.02.
So → 09.02. Mo), was hier zufällig auf dasselbe Fristende führt — das ist
keine Regel, nur eine Eigenschaft dieses Beispiels. Der Hinweis zur im
Dossier `[unverifiziert]` geführten Übertragung der BFH-Rechtsprechung zur
Dreitagesfiktion erscheint in beiden Fällen in der Rechenkette.
**Zweitkontrolle bleibt zwingend.**

### Beispiel 2 — Abgabefrist VZ 2024, beraten

Eingabe: `veranlagungszeitraum: 2024, gruppe: "beraten", bundesland: "NW"`.

| Schritt | Norm | Ergebnis |
|---|---|---|
| EGAO-Sonderfrist VZ 2024 (beraten) | Art. 97 § 36 Abs. 3 Satz 1 Nr. 5 EGAO | 30.04.2026 (Do) |
| kein Wochenend-/Feiertagstreffer | § 108 Abs. 3 AO | unverändert 30.04.2026 |

### Beispiel 3 — Verspätungszuschlag mit Mindestbetrag

Festgesetzte Steuer 1.000 €, keine anzurechnenden Beträge, Fristende
31.07.2026, Abgabe 15.10.2026 → 3 angefangene Monate. 0,25 % von 1.000 €
(= 2,50 €, abgerundet 0 €) liegt unter dem Mindestbetrag von 25 €/Monat →
**75 € Gesamtzuschlag** (3 × 25 €). Pflicht-/Ermessens-Hinweis (§ 152 Abs. 1
/ Abs. 2 AO) wird ungewertet mitgegeben. **Zweitkontrolle bleibt zwingend.**

## Nicht abgedeckt

Diese Regeln sind im Quellen-Dossier `[unverifiziert]` oder als „offen"
geführt und werden **nicht** implementiert — Eingaben, die sie bräuchten,
lehnt der Executor mit Exit-Code 2 ab:

- **Dreitagesfiktion vor dem 01.01.2025** (§ 122 Abs. 2 Nr. 1 AO a. F.): im
  Dossier nur über eine Sekundärquelle belegt. `aufgabe_zur_post_datum`
  vor diesem Datum wird abgelehnt — Bekanntgabedatum direkt angeben.
- **Verschiebung des Bekanntgabe-Fiktionstags selbst** nach § 108 Abs. 3 AO
  bei der seit 2025 geltenden Viertagesfiktion: nur über die ältere
  BFH-Entscheidung zur Dreitagesfiktion (BFH v. 14.10.2003, IX R 68/98)
  hergeleitet, im Dossier `[unverifiziert]`. Über die Option
  `fiktion_verschieben` (Default `false`) einstellbar, mit Hinweis in der
  Rechenkette.
- **Abgabefrist für Land- und Forstwirte ab VZ 2025**: hängt vom
  individuellen Wirtschaftsjahresende ab (§ 149 Abs. 2 Satz 2 AO) — im
  Dossier nicht als feste Regel belegt (nur die EGAO-Tabellenwerte für VZ
  2020–2024 sind belegt und implementiert).
- **Verspätungszuschlag, EGAO-Sonderfristen für Pflichtfestsetzung** (Art.
  97 § 36 Abs. 3 Nr. 5 EGAO, VZ 2020–2024): die genaue Zuordnung der
  Monatsgrenzen (20/19/17/16) zu den einzelnen Veranlagungszeiträumen ist
  im Dossier nicht eindeutig pro Jahr ausgewiesen — wird nicht berechnet.
  Nur die permanente Regelgrenze (§ 152 Abs. 2 Nr. 1/2 AO, 14/19 Monate)
  wird als reiner Normenhinweis ausgegeben, ohne Schwellenwert-Prüfung.
- **Pflicht- vs. Ermessensfall des Verspätungszuschlags** (§ 152 Abs. 1
  vs. Abs. 2 AO): nur als Normenhinweis, keine Bewertung/Subsumtion.
- **§ 152 Abs. 8 Nr. 1 AO** (Ausnahme für monatliche/vierteljährliche
  Steueranmeldungen): der Verspätungszuschlag-Rechner ist nur für
  Jahressteuererklärungen vorgesehen; für USt-VA/LSt-Anmeldung gilt Abs. 5
  laut Gesetz nicht — Hinweis wird ausgegeben, keine eigene Berechnung.
- **Wortlaut § 1 Abs. 15 EGAO** (Übergangsregel Viertagesfiktion) und
  **AEAO-Volltext** zu § 122 AO: nur die Existenz, nicht der Wortlaut ist
  belegt — nicht Teil der Rechenlogik.
- **Rundung der Verspätungszuschlag-Bemessungsgrundlage**: das Dossier
  zitiert § 152 Abs. 5 Satz 2 AO gekürzt (mit „…"); dieser Rechner rundet
  Bemessungsgrundlage und Monatsbetrag konservativ auf volle Euro ab —
  eine dokumentierte Annahme, keine primärbelegte Vorschrift.
- **„Bankarbeitstag"** bei der SV-Fälligkeit (§ 23 Abs. 1 Satz 2 SGB IV):
  im Dossier nicht definiert; dieser Rechner versteht darunter einen
  Werktag ohne bundesweiten gesetzlichen Feiertag (bundesweit statt
  landesspezifisch, da das Interbanken-Clearing nicht landesabhängig ist)
  — eine dokumentierte Annahme.
- **Rhythmus-Bestimmung** bei USt-VA/LSt-Anmeldung aus der Vorjahressteuer
  (§ 18 Abs. 2 UStG / § 41a Abs. 2 EStG): wird nicht aus einem Steuerbetrag
  hergeleitet, sondern als Eingabe (`rhythmus`) verlangt — Kanzleiwissen.

## Quellenstand

Alle implementierten Regeln sind gegen Primärquellen (Gesetzestext, BMF,
BFH) belegt im Dossier
`Steuer-Ops DE/dossier-ao-fristen-stbvv-2026-09-08.md` (Vault, 2026-09-08).
Jede Katalogzeile in
[`fristarten.json`](../../core/calc/ao_fristen/fristarten.json),
[`abgabefristen.json`](../../core/calc/ao_fristen/abgabefristen.json) und
[`vorauszahlungstermine.json`](../../core/calc/ao_fristen/vorauszahlungstermine.json)
trägt `norm`, `quelle_url` und `geprueft_am` (2026-09-08) aus diesem Dossier.
**Gegenlesen durch den Maintainer offen** — Status `beta`, keine händische
Abnahme.

## Bewusste Grenzen

- **Keine Zustellungsfiktionen außerhalb § 122 Abs. 2 Nr. 1/2a AO**: das
  `bekanntgabe_datum`/`aufgabe_zur_post_datum` ist Eingabe und fachlich zu
  bestimmen.
- **Feiertagsregeln**: aktuelle Rechtslage (Stand siehe
  `core/calc/feiertage/rechner.py`, `STAND`); für Jahre vor 1995 warnt der
  Report statt falsche Sicherheit vorzutäuschen.
- **Uhrzeiten**: Fristen enden mit Ablauf des letzten Tages; tagesgenau,
  keine Stundenfristen (§ 108 Abs. 6 AO nicht abgebildet).
