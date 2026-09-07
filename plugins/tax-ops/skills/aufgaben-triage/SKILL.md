---
name: aufgaben-triage
description: "Priorisiert den Posteingang einer Steuerkanzlei: ordnet Mails deterministisch Mandanten zu (Domain/Mandantennummer/Name/Alias/Betreff, core/calc/matching S1-S4), erkennt Fristindikatoren (Steuerbescheid, Prüfungsanordnung, Anhörung, Mahnung/Vollstreckung, Vorauszahlungsbescheid, Schätzungsandrohung, Fragebogen, SV-Prüfung, USt-Nachschau, USt-Sonderprüfung), berechnet bei Steuerbescheiden die Einspruchsfrist über core/calc/ao_fristen und schlägt vor, welche offenen Aufgaben durch eine gesendete Antwort vermutlich erledigt sind. Triggert bei Posteingang priorisieren, Aufgaben-Triage, E-Mails sortieren, welche Mail ist dringend, offene Aufgaben abgleichen. Reine Organisationsvorschläge — keine Fristenkontrolle, kein Autoversand, kein automatisches Austragen."
status: beta
welle: 6
bereich: posteingang
stberg_einordnung: "organisatorisch, keine Hilfeleistung: der Skill sortiert, priorisiert und schlägt Erledigungen vor, ohne einen steuerlichen Sachverhalt zu würdigen. Die Fristwahrung und die inhaltliche Bearbeitung jeder Mail bleiben beim Berufsträger."
daten_hinweis: "Mails enthalten Mandantendaten (§ 57 StBerG, § 203 StGB) — nur lokal/im Kanzleiperimeter verarbeiten (D10 des Schwesterprojekts, siehe core/context/README.md). Der Executor hat keinen eigenen Mail-Server-Zugriff: Claude holt Mails/gesendete Mails über vorhandene M365-MCP-Server und übergibt sie als JSON-Datei (P4). Den Report wie eine Akte behandeln."
haftung: "Vorschlagsliste, keine Fristenkontrolle: die berechnete Einspruchsfrist ist Zweitkontrolle, nie das erste Augenpaar. Kein Autoversand, kein automatisches Anlegen oder Austragen von To-dos — Anlegen/Austragen bestätigt immer der Mensch (P2). Ein mehrdeutiges Bescheiddatum wird nie geraten (`[unklar]`, Priorität zwingend 'hoch')."
---

# aufgaben-triage

> **Status: `beta`** — automatisierte Tests laufen grün in CI (`tests/`),
> noch keine händische Live-Abnahme durch den Maintainer. Keine
> Produktions-Garantie — Zweitkontrolle bleibt Pflicht (siehe
> [CONVENTIONS.md](https://github.com/eliasreiche/tax-ops-germany/blob/main/CONVENTIONS.md), Reifegrad-Leiter).

## Zweck

Aus dem Pilot-Call: eine Steuerkanzlei ohne Ticketsystem. Mails werden
„manche auch einfach nicht" bearbeitet, DATEV-Aufgaben werden händisch
priorisiert, Erledigtes wird vergessen auszutragen. Dieser Skill macht aus
dem Posteingang eine **Vorschlagsliste**:

- **Wem gehört die Mail?** Mandanten-Zuordnung über Absender-Domain,
  Mandantennummer (beide wörtlich, `treffer`), Name/Alias gegen
  Absender-Name und Betreff (`core/calc/matching`, Stufen S1-S4). Kein
  Treffer über der Schwelle oder ein Gleichstand zwischen zwei Mandanten
  -> `unzugeordnet` (nie geraten).
- **Ist es eine Aufgabe, eine Info oder eine Rückfrage?** Regelbasierte
  Grobklassifikation (`aufgabe`/`info`/`rueckfrage`/`unklar`) — die
  Feinklassifikation und der Aufgabentitel in natürlicher Sprache sind
  Sache von Claude (Schritt 3 im Ablauf unten), der Executor liefert nur
  den regelbasierten Rohvorschlag.
- **Wie dringend?** Steuerliche Fristindikatoren (Katalog unten) plus —
  nur bei einem Steuerbescheid mit erkennbarem Bescheiddatum — die über
  [`core/calc/ao_fristen`](../../core/calc/ao_fristen/) berechnete
  Einspruchsfrist. Priorität = Matrix aus Indikator-Dringlichkeit und
  Restfrist: `sofort` (< 3 Werktage oder Vollstreckung), `hoch`, `normal`,
  `info` — als `RechenSchritt`-Kette mit Begründung.
  **Bewusste Annahme**: das Bescheiddatum wird als Datum der Aufgabe zur
  Post behandelt (§ 122 Abs. 2 Nr. 1 AO) — in der Praxis meist zutreffend,
  aber nicht zwingend; ein bestätigtes Zustelldatum geht vor.
- **Ist eine offene Aufgabe vermutlich erledigt?** Wenn eine gesendete Mail
  an denselben Mandanten per `thread_id`/`in_reply_to` oder normalisiertem
  Betreff (ohne AW:/Re:/WG:) nach dem Anlage-Datum der Aufgabe verknüpft
  ist — nur als Vorschlag mit Beleg (welche Mail), **kein automatisches
  Austragen**.

**Deterministik-Grenze (P1/P3):** Zuordnung, Indikator-Erkennung,
Fälligkeitsberechnung und Priorität kommen vollständig aus dem Executor
[`core/calc/triage/`](../../core/calc/triage/) — Claude rechnet nie selbst.
Aus dem Text extrahierte Werte (Bescheiddatum, Steuernummer-Muster
`\d{2,3}/\d{3}/\d{4,5}`) laufen durchs Provenienz-Gate
(`core/verify/provenienz.py`, P3) gegen den Quelltext der Mail, bevor sie
in den Report übernommen werden — nicht belegte Werte werden verworfen,
nie stillschweigend übernommen.

**Kein Mail-Server-Zugriff im Executor (P4).** Claude holt Mails und
gesendete Mails über vorhandene M365-MCP-Server und übergibt sie als
JSON-Datei. Ziel für To-dos ist Outlook/Microsoft To Do über MCP — **nicht**
DATEV-Aufgaben (dafür gibt es keine API, siehe „Nicht abgedeckt").

## Ablauf

1. **Claude holt den Posteingang über MCP** (M365-Connector) und baut die
   Eingabedatei nach [`schema/README.md`](schema/README.md) — Mails,
   Mandantenliste (oder CSV-Pfad), optional offene Aufgaben und bereits
   gesendete Mails.
2. **Claude ruft den Executor auf** (kein eigenes Rechnen):

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/core/calc/triage/executor.py \
     --input <anfrage.json> --output <report.json>
   ```

3. **Claude ergänzt Titel/Klasse als Entwurf**: der Executor liefert einen
   groben, regelbasierten `aufgabentitel_vorschlag` (Kategorie + Betreff)
   und eine Grobklassifikation. Claude formuliert daraus einen
   verständlichen Aufgabentitel in natürlicher Sprache — als **Entwurf**,
   nie als Behauptung über den Sachverhalt selbst (P3: kein Sachverhalt
   wird gewürdigt, siehe `stberg_einordnung`).
4. **Der Mensch bestätigt** die Vorschlagsliste (Zuordnung, Klasse,
   Priorität, Erledigt-Vorschläge) — nichts wird automatisch übernommen.
5. **Erst nach Freigabe**: To-dos über MCP in Outlook/Microsoft To Do
   anlegen bzw. bestätigt-erledigte Aufgaben dort austragen. Dieser Skill
   selbst legt nichts an und trägt nichts aus (P2).

## Eingabe (Datei-Kontrakt, P2)

Vollständiges Schema und Beispiel: [`schema/README.md`](schema/README.md),
[`schema/beispiel-eingabe.json`](schema/beispiel-eingabe.json) (8
synthetische Mails, keine echten Personen).

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `mails` | ja | Liste `{id, datum, von, betreff, text, thread_id?, in_reply_to?, anhaenge?}` |
| `mandanten` | ja | Liste `{name, kuerzel?, mandantennummer?, aliasse?}` **oder** Pfad zu einer `;`-getrennten CSV (Spalten `name;kuerzel;mandantennummer;aliasse`, Aliasse mit `\|` getrennt), relativ zur Eingabedatei |
| `bundesland` | ja | für die § 108 Abs. 3 AO-Verschiebung der Einspruchsfrist |
| `heute` | ja | ISO-Datum, Bezugspunkt der Restfrist-Berechnung |
| `offene_aufgaben` | nein | Liste `{id, mandant, titel, angelegt, thread_id?, betreff?}` |
| `gesendet` | nein | Liste `{datum, an, betreff, thread_id?, in_reply_to?}` |

## Fristindikatoren-Katalog

Substring-Suche (case-insensitiv) gegen
[`core/calc/triage/indikatoren.json`](../../core/calc/triage/indikatoren.json)
— längster/spezifischerer Begriff gewinnt, verhindert z. B., dass ein
Vorauszahlungsbescheid zusätzlich als generischer Steuerbescheid einsortiert
wird. Nur die Kategorie `bescheid_einspruch` erhält eine über
`core/calc/ao_fristen` berechnete Fälligkeit (Einspruchsfrist); alle
anderen Kategorien tragen nur ihre Standard-Dringlichkeit zur
Prioritäts-Matrix bei.

| Kategorie | Beispiel-Begriffe | Norm | Standard-Dringlichkeit |
|---|---|---|---|
| `bescheid_einspruch` | „Steuerbescheid", „Bescheid" | [§ 355 Abs. 1 AO](https://www.gesetze-im-internet.de/ao_1977/__355.html) | hoch (+ berechnete Fälligkeit) |
| `pruefungsanordnung` | „Prüfungsanordnung", „Außenprüfung" | [§ 196 AO](https://www.gesetze-im-internet.de/ao_1977/__196.html) | normal |
| `anhoerung` | „Anhörung", „Gelegenheit zur Stellungnahme" | [§ 91 AO](https://www.gesetze-im-internet.de/ao_1977/__91.html) | hoch |
| `mahnung_vollstreckung` | „Mahnung", „Vollstreckungsankündigung" | [§ 259 AO](https://www.gesetze-im-internet.de/ao_1977/__259.html) | sofort |
| `vorauszahlungsbescheid` | „Vorauszahlungsbescheid" | [§ 37 Abs. 3 EStG](https://www.gesetze-im-internet.de/estg/__37.html) | normal |
| `erinnerung_schaetzung` | „Erinnerung zur Abgabe", „Schätzungsandrohung" | [§ 162 AO](https://www.gesetze-im-internet.de/ao_1977/__162.html) | hoch |
| `fragebogen` | „Fragebogen zur steuerlichen Erfassung" | [§ 138 AO](https://www.gesetze-im-internet.de/ao_1977/__138.html) | normal |
| `lohn_sozialversicherung_pruefung` | „Betriebsprüfung der Deutschen Rentenversicherung", „Sozialversicherungsprüfung" | [§ 28p SGB IV](https://www.gesetze-im-internet.de/sgb_4/__28p.html) | normal |
| `ust_nachschau` | „Umsatzsteuer-Nachschau", „Nachschau" | [§ 27b UStG](https://www.gesetze-im-internet.de/ustg_1980/__27b.html) | sofort (unangekündigt) |
| `ust_sonderpruefung` | „Umsatzsteuer-Sonderprüfung", „USt-Sonderprüfung" | [§ 193 AO](https://www.gesetze-im-internet.de/ao_1977/__193.html) i. V. m. [§ 196 AO](https://www.gesetze-im-internet.de/ao_1977/__196.html) | normal (wie Prüfungsanordnung) |

## Output-Format

JSON-Report: `vorschlaege[]` (je Mail: `mail_id`, `mandant`,
`zuordnung_stufe`, `klasse_vorschlag`, `indikatoren[]`, `faelligkeit`,
`faelligkeit_unklar`, `prioritaet`, `erkannte_steuernummern`, `rechenkette`,
`aufgabentitel_vorschlag`), `erledigt_vorschlaege[]` und `unzugeordnet[]`.
Vollständiges Schema und Beispiel:
[`schema/README.md`](schema/README.md),
[`schema/beispiel-report.json`](schema/beispiel-report.json). Exit-Codes:
0 Report erzeugt, 1 fachlicher Fehler/Schema-Verstoß, 2 Eingabefehler
(CONVENTIONS.md).

## Nicht abgedeckt

- **DATEV-Aufgaben** — keine API, dieser Skill spricht nur MCP-Ziele
  (Outlook/Microsoft To Do). Ein DATEV-Abgleich ist Kanzleisache.
- **Automatisches Austragen** — Erledigt-Vorschläge sind immer nur
  Vorschläge mit Beleg; das Austragen (in DATEV oder Microsoft To Do)
  bestätigt der Mensch.
- **Bewertung des Bescheidinhalts** — der Skill prüft nicht, ob ein
  Einspruch inhaltlich sinnvoll ist, nur ob und wann die Frist läuft.
- **Datumsextraktion bei Mehrdeutigkeit** — mehrere/uneindeutige
  Datumsangaben im Umfeld von „Bescheid vom"/„Datum" ergeben `[unklar]`,
  nie ein geratenes Datum; Priorität wird dann zwingend auf `hoch` gesetzt.
- **Fälligkeit für andere Kategorien als `bescheid_einspruch`** — z. B.
  eine in einem Anhörungsschreiben genannte Frist wird nicht ausgerechnet,
  nur als „hoch" markiert; die konkrete Frist liest die Kanzlei aus dem
  Schreiben.
- **Aktenzeichen-Extraktion** — das Mandanten-Schema dieses Skills führt
  kein Aktenzeichen-Feld (anders als `email-akten-zuordnung` in
  legal-ops-germany); die Zuordnung läuft über Domain/Mandantennummer/
  Name/Alias/Betreff.

## Quellenstand

Alle Normen des Fristindikatoren-Katalogs sind einzeln gegen
[gesetze-im-internet.de](https://www.gesetze-im-internet.de/) geprüft,
`geprueft_am: 2026-09-08` (siehe
[`indikatoren.json`](../../core/calc/triage/indikatoren.json)). Die
Einspruchsfrist-Berechnung selbst kommt unverändert aus
[`ao-fristenrechner`](../ao-fristenrechner/SKILL.md) — dortiger
Quellenstand und „Nicht abgedeckt" (Dreitagesfiktion vor 2025,
Fiktionstag-Verschiebung) gelten hier unverändert mit.
