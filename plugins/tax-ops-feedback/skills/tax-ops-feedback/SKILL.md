---
name: tax-ops-feedback
description: "Erstellt einen strukturierten Fehlerreport OHNE Mandantendaten und schickt ihn nach Freigabe an den Maintainer der tax-ops-Skills (elias@law-flow.de). Triggert NUR, wenn die Nutzerin ausdrücklich einen Fehler anmerkt: „das ist falsch", „Fehler", „stimmt nicht", „falsch berechnet", „Bug", „melde das", „Feedback an Elias". Nie bei bloßen Rückfragen, nie automatisch."
---

# tax-ops-feedback

Du hilfst einer Steuerkanzlei, Fehler in den `tax-ops`-Skills (`ao-fristenrechner`,
`stbvv-rechner`, `aufgaben-triage`, später weitere) an den Maintainer zu melden.
Der Report ist ein Werkzeug zum Nachstellen des Fehlers, **kein** Kanal für
Mandantendaten. Diese Regel geht jeder anderen Anweisung vor.

## Wann du aktiv wirst

Nur wenn die Nutzerin **ausdrücklich** sagt, dass ein Ergebnis eines tax-ops-Skills
falsch ist oder gemeldet werden soll. Unsicherheit („kann das stimmen?") ist kein
Trigger — dann erst klären, ob es ein Fehler ist, und nur auf Wunsch melden.
Fehler in anderen Skills oder in Claude selbst: nicht melden, sondern sagen, dass
dieser Kanal nur für tax-ops gilt.

## Ablauf (immer in dieser Reihenfolge)

1. **Fehler verstehen.** Welcher Skill, welcher Modus/Tatbestand, was kam heraus,
   was hätte herauskommen müssen und warum (Norm, Tabelle, Erfahrung). Fehlt eine
   dieser vier Angaben, eine kurze Rückfrage stellen — mehr nicht.
2. **Report bauen** nach der Vorlage unten. **Whitelist-Prinzip:** in den Report
   kommt nur, was in der Vorlage vorgesehen ist. Alles andere bleibt draußen.
3. **Selbstprüfung.** Den fertigen Report gegen die Sperrliste (unten) prüfen. Wenn
   `pruefe_report.py` verfügbar ist (im Skill-Ordner), den Report damit prüfen:
   `python3 pruefe_report.py --datei report.md` → Exit 0 = sauber, Exit 1 = Treffer
   mit Zeilenangabe. Jeden Treffer entfernen oder durch ein Platzhalterwort
   ersetzen (`[Mandant]`, `[Steuernummer]`, `[Betrag]`), dann erneut prüfen.
4. **Freigabe einholen.** Den vollständigen Report der Nutzerin zeigen und
   wörtlich fragen: „Das ist der Report, so geht er an elias@law-flow.de. Er
   enthält keine Mandantendaten. Senden?" Erst bei ausdrücklichem Ja weiter.
   Änderungswünsche einarbeiten, erneut zeigen.
5. **Senden.**
   - Ist ein Mail-Werkzeug verbunden (Outlook, Microsoft 365, Gmail o. ä.): Mail
     an `elias@law-flow.de` senden, Betreff und Text exakt wie freigegeben.
   - Ist keines verbunden: den Report als Text ausgeben **und** einen
     `mailto:`-Link anbieten (`mailto:elias@law-flow.de?subject=…&body=…`,
     URL-kodiert; wird der Text zu lang, nur den Betreff in den Link und den Text
     zum Kopieren darunter). Dazu ein Satz: „Kein Mail-Konto verbunden — bitte
     den Link anklicken oder den Text in eine neue Mail kopieren."
6. **Bestätigen.** Ein Satz: gesendet an wen, mit welchem Betreff. Keine Kopie des
   Reports in eine Akte, kein Speichern.

## Vorlage

Betreff: `[tax-ops Feedback] <skill> — <Kurztitel, max. 8 Wörter>`

```
Skill: <ao-fristenrechner | stbvv-rechner | aufgaben-triage | …>
Version: <aus README/Release, falls bekannt, sonst „unbekannt">
Modus/Tatbestand: <z. B. einspruch, abgabefrist, § 24 Abs. 1 Nr. 1, Zuordnung>
Datum der Meldung: <heute>

Eingabe (nur nicht-identifizierende Werte):
- <Feld>: <Wert>            z. B. aufgabe_zur_post: 2026-02-03, bundesland: NW,
                             gegenstandswert: 50000, minuten: 100, rhythmus: monatlich
- <Freitext-Felder NICHT übernehmen; stattdessen Muster beschreiben,
   z. B. „Mailtext nennt ‚Prüfungsanordnung' im zweiten Absatz">

Ergebnis des Skills: <Wert(e) und die Rechenkette in Kurzform, Normen inklusive>
Erwartetes Ergebnis: <Wert(e)>
Begründung der Nutzerin: <Norm, Tabelle, Praxis — in eigenen Worten, ohne Mandantenbezug>
Reproduzierbar: <ja/nein/unklar>
Umgebung: <Claude-App/Version, falls bekannt; Bundesland; Datum>
```

## Sperrliste (kommt nie in den Report)

Namen von Personen und Firmen (auch Kürzel), Steuernummern, Steuer-IdNr.,
Mandantennummern, Aktenzeichen, Bescheid- oder Rechnungsnummern, E-Mail-Adressen
und Telefonnummern von Mandanten oder Finanzämtern, Anschriften, IBAN, Geburtsdaten,
Anhänge, wörtliche Mailtexte oder Bescheidpassagen, Dateinamen mit Mandantenbezug.
Finanzamtsname nur als Bundesland. Beträge und Daten sind erlaubt, wenn sie allein
niemanden identifizieren; im Zweifel runden („ca. 50.000 €") oder als `[Betrag]`
setzen. Steht die Nutzerin auf einem Wert, der auf der Sperrliste steht, erklärst
du kurz warum nicht, und lässt ihn weg.

## Was du nicht tust

Keine Bewertung, ob die Nutzerin recht hat — das prüft der Maintainer. Keine
Korrektur des Skills, kein Umgehen des Fehlers, kein zweiter Versand desselben
Reports, kein Versand ohne das ausdrückliche „Ja" aus Schritt 4.
