# core/calc — geteilte deterministische Rechner

Ein Rechner, viele Skills — keine Duplikation. Snapshot aus
`legal-ops-germany` (siehe [`../VENDORED.md`](../VENDORED.md)); Tests liegen
unter [`../tests/`](../tests/).

| Modul | Inhalt |
|---|---|
| [`cli.py`](cli.py) | Gemeinsame CLI-Bausteine (Argument-Parsing, JSON-Ein-/Ausgabe) für Executor-Skripte. |
| [`datum.py`](datum.py) | Datums-Parsing/-Kanonisierung: ISO, ausgeschriebenes Deutsch, RFC-2822-Mail-Header. |
| [`rechenschritt.py`](rechenschritt.py) | `RechenSchritt`-Datenklasse — Baustein jeder nachvollziehbaren Rechenkette (P1). |
| [`slug.py`](slug.py) | Slug-Normalisierung (z. B. für Dateinamen). |
| [`parteien.py`](parteien.py) | Parteien-/Mandantenlisten-Parsing aus CSV/JSON. |
| [`feiertage/`](feiertage/) | Gesetzliche Feiertage aller 16 Bundesländer, berechnet (Gaußsche Osterformel), teilgebietliche Feiertage ehrlich gekennzeichnet. |
| [`matching/`](matching/) | Fuzzy-Ähnlichkeit, Kölner Phonetik, Namens-Normalisierung und deren Kombination zum Namensvergleich. |
| [`zuordnung/`](zuordnung/) | Dokument-Metadaten → Mandats-Kandidaten: Aktenzeichen-Suche, Parteiname-in-Text-Suche, Kombination. |

Steuerspezifische Rechner (`ao-fristenrechner`, `stbvv-rechner`, …) entstehen
hier neu ab Welle 6 — siehe [`../../skills/README.md`](../../skills/README.md).
