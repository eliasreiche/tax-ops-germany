# Schema — aufgaben-triage

Datei-Kontrakt (P2) für den Executor
[`core/calc/triage/executor.py`](../../../core/calc/triage/executor.py).
Kein Netzwerkzugriff, keine Datenbank, kein Mail-Server-Zugriff (P4) — JSON-
Datei rein, JSON-Report raus.

## Eingabe

```json
{
  "mails": [
    {
      "id": "mail-001",
      "datum": "2026-08-10",
      "von": "Finanzamt Beispielstadt <poststelle@fa-beispielstadt.example>",
      "betreff": "Steuerbescheid Backstube Sonnenschein GmbH",
      "text": "... Bescheid vom 10.08.2026 ...",
      "thread_id": "thread-1",
      "in_reply_to": "mail-000",
      "anhaenge": ["bescheid.pdf"]
    }
  ],
  "mandanten": [
    {
      "name": "Backstube Sonnenschein GmbH",
      "kuerzel": "BSS",
      "mandantennummer": "12/345/67890",
      "aliasse": ["backstube-sonnenschein.example"]
    }
  ],
  "offene_aufgaben": [
    {"id": "aufgabe-001", "mandant": "Backstube Sonnenschein GmbH",
     "titel": "Lohnunterlagen anfordern", "angelegt": "2026-08-28",
     "thread_id": "thread-lohnunterlagen-001"}
  ],
  "gesendet": [
    {"datum": "2026-09-07", "an": "p.beispiel@backstube-sonnenschein.example",
     "betreff": "AW: Lohnunterlagen anfordern", "thread_id": "thread-lohnunterlagen-001"}
  ],
  "bundesland": "NW",
  "heute": "2026-09-08"
}
```

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `mails[].id` | ja | eindeutige Kennung, wird 1:1 in den Report übernommen |
| `mails[].datum` | ja | Mail-Datum (nicht das Bescheiddatum — das steht im Text und wird extrahiert) |
| `mails[].von` | ja | `"Name <adresse>"` oder nur eine Adresse (stdlib `email.utils.parseaddr`) |
| `mails[].betreff`, `.text` | ja | Grundlage für Zuordnung, Indikator-Erkennung, Bescheiddatum/Steuernummer-Extraktion |
| `mails[].thread_id`, `.in_reply_to` | nein | für den Erledigt-Abgleich gegen `gesendet[]` |
| `mails[].anhaenge` | nein | wird durchgereicht, aber nicht ausgewertet (kein OCR in diesem Skill) |
| `mandanten` | ja | Liste **oder** ein String — dann Pfad zu einer `;`-getrennten CSV (Spalten `name;kuerzel;mandantennummer;aliasse`, `aliasse` mit `\|` getrennt, UTF-8, Kopfzeile Pflicht — siehe `core/calc/parteien.py`), relativ zur Eingabedatei aufgelöst |
| `mandanten[].aliasse` | nein | Namensvarianten **und/oder** eine Domain (z. B. `"mandant.example"`) — eine Domain, die exakt der Absender-Domain entspricht, zählt als stärkster Treffer (`stufe: "domain"`) |
| `offene_aufgaben[]` | nein | `id`, `mandant` (Name wie in `mandanten[].name`), `titel`, `angelegt` (ISO-Datum) Pflicht; `thread_id`/`betreff` optional für den Erledigt-Abgleich |
| `gesendet[]` | nein | `datum`, `an`, `betreff` Pflicht; `thread_id`/`in_reply_to` optional |
| `bundesland` | ja | `BW BY BE BB HB HH HE MV NI NW RP SL SN ST SH TH` — für § 108 Abs. 3 AO |
| `heute` | ja | ISO-Datum, Bezugspunkt der Restfrist-Berechnung |

## Mandanten-Zuordnung (`zuordnung_stufe`)

In dieser Reihenfolge (die erste zutreffende gewinnt), jeweils gegen
Absender-Domain/-Name und Betreff geprüft:

| Stufe | Bedeutung | Kategorie |
|---|---|---|
| `domain` | Absender-Domain == ein Alias, der eine Domain ist | `treffer` |
| `mandantennummer` | `mandantennummer` wörtlich (Whitespace-toleranter Vergleich) in Betreff/Text | `treffer` |
| `S1`-`S4` | Name/Alias gegen Absender-Name/Betreff, siehe [`core/calc/matching`](../../../core/calc/matching/) | `treffer` (S1/S2) bzw. `moeglicher_treffer` (S3/S4) |

Kein Treffer über der S4-Schwelle (Default 0.85) oder ein **Gleichstand**
zwischen zwei Mandanten auf derselben besten Stufe -> die Mail erscheint in
`unzugeordnet[]` (nie geraten).

## Priorität (`prioritaet`) und Fälligkeit (`faelligkeit`)

Nur die Indikator-Kategorie `bescheid_einspruch` erhält eine über
[`core/calc/ao_fristen`](../../../core/calc/ao_fristen/) berechnete
Fälligkeit (Einspruchsfrist, das erkannte Bescheiddatum wird dafür als
Datum der Aufgabe zur Post behandelt, § 122 Abs. 2 Nr. 1 AO). Alle anderen
Kategorien tragen nur ihre `standard_dringlichkeit` bei
([Katalog](../../../core/calc/triage/indikatoren.json)).

| Priorität | Bedingung |
|---|---|
| `sofort` | Restfrist < 3 Werktage **oder** Kategorie `mahnung_vollstreckung` **oder** mehrdeutiges Bescheiddatum kombiniert mit einer weiteren `sofort`-Kategorie |
| `hoch` | Restfrist 3-10 Werktage, **oder** mehrdeutiges Bescheiddatum (`faelligkeit_unklar: true`, immer mindestens `hoch`), **oder** höchste Standard-Dringlichkeit der erkannten Indikatoren ist `hoch` und keine Fälligkeit berechnet wurde |
| `normal` | Restfrist > 10 Werktage, oder kein Indikator und keine Info-/Rückfrage-Klasse |
| `info` | kein Indikator und Newsletter-/„zur Kenntnisnahme"-Muster erkannt |

Jede Entscheidung steht als `RechenSchritt`-Kette in `rechenkette[]`
(Norm/Beschreibung/Ergebnis je Schritt, `quelle: "executor"`) — inklusive
der eingebetteten `ao_fristen`-Rechenkette, falls eine Fälligkeit berechnet
wurde.

## Klassifikation (`klasse_vorschlag`)

Rein regelbasiert (der Executor würdigt keinen Sachverhalt, siehe
`stberg_einordnung` in SKILL.md):

1. **`aufgabe`** — mindestens ein Fristindikator erkannt.
2. **`info`** — kein Indikator, aber ein Newsletter-/Rundschreiben-Muster
   (`newsletter`, `rundschreiben`, `informationsschreiben`, „zur
   Kenntnisnahme", „zur Information").
3. **`rueckfrage`** — kein Indikator, aber ein `?` in Betreff oder Text.
4. **`unklar`** — keiner der obigen Fälle.

Die Feinklassifikation (z. B. „das ist eigentlich eine Terminanfrage") und
der Aufgabentitel in natürlicher Sprache sind **Prompt-Anteil** in
SKILL.md, Ablaufschritt 3 — der Executor liefert nur `klasse_vorschlag` und
einen groben `aufgabentitel_vorschlag` (Kategorie + Betreff, oder nur
Betreff ohne Indikator).

## Provenienz (P3)

`erkannte_steuernummern[]` (Muster `\d{2,3}/\d{3}/\d{4,5}`) und das
Bescheiddatum in `faelligkeit`-Berechnungen laufen durch
[`core/verify/provenienz.py`](../../../core/verify/provenienz.py), bevor
sie in den Report übernommen werden — ein extrahierter Wert, der (nach
Normalisierung) nicht wörtlich in Betreff/Text steht, wird verworfen statt
ausgegeben.

## Erledigt-Vorschlag (`erledigt_vorschlaege[]`)

Eine `offene_aufgabe` gilt als vermutlich erledigt, wenn eine `gesendet`-
Mail **alle** drei Bedingungen erfüllt:

1. **Verknüpft** über `thread_id` (beide gleich), `in_reply_to` (gleich dem
   `thread_id` der Aufgabe) oder normalisierten Betreff (führende
   `Re:`/`AW:`/`WG:`-Präfixe entfernt, Groß-/Kleinschreibung egal).
2. **Zeitlich danach**: `gesendet.datum` > `aufgabe.angelegt` (ISO-Vergleich).
3. **An denselben Mandanten**: `gesendet.an` löst über dieselbe
   Zuordnungslogik wie oben auf denselben Mandantennamen auf wie
   `aufgabe.mandant`.

Nur ein **Vorschlag mit Beleg** (`beleg`: welche gesendete Mail, `match_art`)
— kein automatisches Austragen (P2).

## Beispiele

[`beispiel-eingabe.json`](beispiel-eingabe.json) (8 synthetische Mails,
`.example`-Domains, keine echten Personen) und der dazu passende
[`beispiel-report.json`](beispiel-report.json), erzeugt mit:

```bash
python3 core/calc/triage/executor.py \
  --input schema/beispiel-eingabe.json --output schema/beispiel-report.json
```
