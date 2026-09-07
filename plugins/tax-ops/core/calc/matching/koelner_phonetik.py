"""koelner_phonetik — Kölner Phonetik nach der Standard-Definition (P3-Bibliothek).

Implementiert das phonetische Kodierungsverfahren von Hans Joachim Postel
(1969) zur lautähnlichen Indexierung deutscher Wörter (insbesondere
Personennamen). Reine Standardbibliothek, keine Abhängigkeiten.

## Regelwerk

Schritt 1 — Buchstabe für Buchstabe kodieren (Kontextregeln, `vorgänger` und
`nachfolger` beziehen sich jeweils auf den direkt benachbarten Buchstaben im
bereits auf A–Z reduzierten Buchstabenstrom, siehe `_vorbereiten`):

| Buchstabe(n)   | Bedingung                                              | Code |
|----------------|---------------------------------------------------------|------|
| A,E,I,J,O,U,Y  | —                                                        | 0    |
| H              | —                                                         | entfällt (kein Code) |
| B              | —                                                         | 1    |
| P              | nicht vor H                                              | 1    |
| P              | vor H                                                    | 3    |
| D,T            | nicht vor C,S,Z                                          | 2    |
| D,T            | vor C,S,Z                                                | 8    |
| F,V,W          | —                                                         | 3    |
| G,K,Q          | —                                                         | 4    |
| C              | im Anlaut (erster Buchstabe des Worts), vor A,H,K,L,O,Q,R,U,X | 4 |
| C              | nicht im Anlaut, vor A,H,K,O,Q,U,X **und nicht** nach S,Z | 4    |
| C              | in allen anderen Fällen                                  | 8    |
| X              | nicht nach C,K,Q                                         | 48   |
| X              | nach C,K,Q                                               | 8    |
| L              | —                                                         | 5    |
| M,N            | —                                                         | 6    |
| R              | —                                                         | 7    |
| S,Z            | —                                                         | 8    |

Schritt 2 — direkt aufeinanderfolgende gleiche Ziffern werden zu einer
einzigen Ziffer zusammengefasst (wie bei Soundex). `H` trägt keinen Code und
wird dabei komplett übersprungen — zwei durch ein `H` getrennte Buchstaben
mit gleichem Code verschmelzen daher trotzdem (z. B. in "Reihe": nicht
relevant hier, aber Regelbestandteil).

Schritt 3 — alle Ziffern `0` werden aus dem Ergebnis entfernt, **außer** der
allerersten Ziffer der Kette (die bleibt auch dann erhalten, wenn sie `0`
ist, damit vokalisch beginnende Wörter nicht ihre erste Stelle verlieren).

## Vorverarbeitung

Umlaute werden vor der Kodierung wie ihr Grundvokal behandelt (ä→a, ö→o,
ü→u — beide fallen in die Vokalgruppe 0). `ß` wird über `str.upper()` bereits
zu `SS` (Standard-Unicode-Großschreibung in Python) und fällt damit in die
S/Z-Gruppe (Code 8) — konsistent mit einem einzelnen `s`. Alle Zeichen
außerhalb A–Z (Leerzeichen, Bindestriche, Ziffern, Interpunktion) werden vor
der Kodierung entfernt; der Buchstabenstrom wird dadurch **zusammenhängend**
behandelt — ein Bindestrich in einem zusammengesetzten Namen unterbricht die
Kodierung nicht (Referenzfall unten).

## Referenzfälle (dokumentiert, siehe tests/)

- "Müller-Lüdenscheidt" → "65752682" (Standard-Lehrbuchbeispiel des
  Verfahrens).
- "Meyer" = "Maier" = "Mayr" = "Meier" → "67" (klassische Schreibweisen-
  Äquivalenzklasse, der Hauptanwendungsfall der Kölner Phonetik).
- "Schmidt" = "Schmitt" → "862".

## Grenzen

- Das Verfahren ist für **deutsche** Lautung entwickelt; bei fremdsprachigen
  Namen (nicht-deutsche Aussprachekonventionen) ist die Trefferqualität nicht
  belastbar — dokumentierte Grenze, kein Ausschluss.
- Wörter ohne kodierbare Buchstaben (z. B. reine Zahlen/Symbole) ergeben
  einen leeren Code `""`. Zwei leere Codes sind bewusst **kein** Treffer —
  der Vergleich in `matching/vergleich.py` (Stufe S3) verwirft sie, sonst
  gälten zwei beliebige unkodierbare Tokens als phonetisch identisch.
"""
from __future__ import annotations

_VOKALE = "AEIJOUY"
_UMLAUT_ZU_VOKAL = str.maketrans({"Ä": "A", "Ö": "O", "Ü": "U"})


def _vorbereiten(wort: str) -> list[str]:
    """Großschreibung, Umlaut→Vokal, ß→SS (via str.upper()), nur A–Z behalten."""
    grossgeschrieben = wort.upper().translate(_UMLAUT_ZU_VOKAL)
    return [ch for ch in grossgeschrieben if "A" <= ch <= "Z"]


def _kodiere_buchstabe(buchstabe: str, ist_anlaut: bool,
                        vorgaenger: str | None, nachfolger: str | None) -> str:
    if buchstabe in _VOKALE:
        return "0"
    if buchstabe == "H":
        return ""
    if buchstabe == "B":
        return "1"
    if buchstabe == "P":
        return "3" if nachfolger == "H" else "1"
    if buchstabe in "DT":
        return "8" if nachfolger in ("C", "S", "Z") else "2"
    if buchstabe in "FVW":
        return "3"
    if buchstabe in "GKQ":
        return "4"
    if buchstabe == "C":
        if ist_anlaut:
            return "4" if (nachfolger is not None and nachfolger in "AHKLOQRUX") else "8"
        if (nachfolger is not None and nachfolger in "AHKOQUX"
                and vorgaenger not in ("S", "Z")):
            return "4"
        return "8"
    if buchstabe == "X":
        return "8" if vorgaenger in ("C", "K", "Q") else "48"
    if buchstabe == "L":
        return "5"
    if buchstabe in "MN":
        return "6"
    if buchstabe == "R":
        return "7"
    if buchstabe in "SZ":
        return "8"
    return ""  # unerreichbar, falls _vorbereiten sauber auf A-Z reduziert hat


def _reduziere_wiederholungen(ziffernkette: str) -> str:
    """Schritt 2: direkt aufeinanderfolgende gleiche Ziffern zusammenfassen."""
    ergebnis: list[str] = []
    for ziffer in ziffernkette:
        if not ergebnis or ergebnis[-1] != ziffer:
            ergebnis.append(ziffer)
    return "".join(ergebnis)


def _entferne_nullen_ausser_erster(ziffernkette: str) -> str:
    """Schritt 3: alle '0' entfernen, außer an allererster Stelle."""
    if not ziffernkette:
        return ziffernkette
    return ziffernkette[0] + ziffernkette[1:].replace("0", "")


def code(wort: str) -> str:
    """Berechnet den Kölner-Phonetik-Code für `wort` (siehe Modul-Docstring).

    Arbeitet auf dem gesamten übergebenen String als einem zusammenhängenden
    Buchstabenstrom (Leerzeichen/Bindestriche werden vorab entfernt, siehe
    `_vorbereiten`) — für mehrwortige Namen ruft die aufrufende Stelle diese
    Funktion je Token separat auf (S3-Stufe des Matching-Executors: "Kölner
    Phonetik je Token").
    """
    buchstaben = _vorbereiten(wort)
    n = len(buchstaben)
    ziffern: list[str] = []
    for i, buchstabe in enumerate(buchstaben):
        vorgaenger = buchstaben[i - 1] if i > 0 else None
        nachfolger = buchstaben[i + 1] if i + 1 < n else None
        ziffern.append(_kodiere_buchstabe(buchstabe, i == 0, vorgaenger, nachfolger))
    ziffernkette = "".join(ziffern)
    reduziert = _reduziere_wiederholungen(ziffernkette)
    return _entferne_nullen_ausser_erster(reduziert)
