"""zuordnung.parteisuche — Parteiname-in-Text-Suche, Stufen Z1-Z4 (P3-Bibliothek).

Sucht, ob ein Mandats-Parteiname (`mandant`/`gegenseite`) irgendwo in einem
Dokument-Textfeld (Betreff, Textauszug, Absendername) vorkommt. Nutzt die
Normalisierungs- und Ähnlichkeits-Bausteine aus
[`core/calc/matching`](../matching/) — dieselbe Bibliothek, die
`interessenkollision-check` für den Parteien-Abgleich S1-S4 verwendet
(siehe dortiges `schema/README.md`) — kombiniert sie hier aber anders:

`interessenkollision-check` vergleicht **Name gegen Name** (zwei kurze
Strings). Hier wird **Name gegen Fließtext** geprüft (ein kurzer Name
gegen einen ganzen Betreff/Textauszug) — deshalb Token-Mengen-**Teilmenge**
statt -Gleichheit und ein **Bestes-Token-Match** je Namens-Token statt
1:1-Alignment über die gesamte Tokenliste (`token_alignment_ratio` würde
bei einem langen Text durch die Normierung auf die längere Tokenliste
praktisch nie ansprechen).

Vier Stufen, absteigend in Sicherheit, aufsteigend im Rückruf — die erste
zutreffende Stufe gewinnt (Deterministik-Grenze, P3):

    Z1  der gesamte normalisierte Name kommt als zusammenhängende,
        wortgrenzenbegrenzte Phrase im normalisierten Text vor  -> treffer
    Z2  alle normalisierten Namens-Tokens kommen (in beliebiger
        Reihenfolge) irgendwo als Tokens im Text vor             -> treffer
    Z3  zu jedem Namens-Token existiert ein Text-Token mit
        identischem Kölner-Phonetik-Code                        -> moeglicher_treffer
    Z4  Durchschnitt der besten Zeichenketten-Ähnlichkeit je
        Namens-Token >= Schwelle (Default 0.85, wie
        interessenkollision-check, dort begründet)               -> moeglicher_treffer

## Bewusste Grenzen (siehe auch core/calc/matching/*.py)

- **Z2/Z3 können bei sehr kurzen/einzeltokenigen Namen falsch positiv
  anschlagen**, wenn der Text zufällig ein gleiches/phonetisch gleiches
  Wort enthält (dasselbe Risiko wie S2/S3 in `interessenkollision-check`,
  hier durch den längeren Fließtext sogar leicht erhöht). Dokumentierter
  Kompromiss zugunsten des Rückrufs — die Kategorie `moeglicher_treffer`
  (Z3/Z4) macht dieses Risiko im Report sichtbar.
- **Rechtsform-Gleichheit allein ist nie ein Treffer** (geerbt von
  `normalisiere()`/`tokenisiere()`): "Müller GmbH" wird nie allein durch
  das gemeinsame Wort "GmbH" mit "Schulze GmbH" gematcht, weil die
  Rechtsform vor dem Tokenisieren gestrippt wird.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

_ZUORDNUNG_DIR = Path(__file__).resolve().parent
_CALC_DIR = _ZUORDNUNG_DIR.parent
if str(_CALC_DIR) not in sys.path:
    sys.path.insert(0, str(_CALC_DIR))

from matching import (  # noqa: E402
    koelner_code,
    normalisiere,
    sequenz_ratio,
    tokenisiere,
)

STUFE_TREFFER = "treffer"
STUFE_MOEGLICH = "moeglicher_treffer"

SCHWELLE_MOEGLICH_DEFAULT = 0.85

# Anreden, die im Fließtext eine natürliche Person markieren (Stufe Z2N,
# siehe `nachname_in_personen_position()`). Geschlossener grammatischer
# Satz — keine pflegebedürftige Datenliste (eine solche bräuchte es für die
# Gegenprobe "ist dieses Token überhaupt ein Nachname?": Orts-, Behörden-
# und Branchenwörter sind nicht aufzählbar). Werte in der Form nach
# `normalisiere()` (klein, transliteriert).
ANREDEN: frozenset[str] = frozenset({"herr", "herrn", "frau"})

# Rubrum-Trenner, die zwei Nachnamen im Fließtext explizit als Parteien
# desselben Rechtsstreits verbinden (Stufe Z2N, siehe
# `nachname_in_personen_position()`). Geschlossene Menge wie ANREDEN oben —
# bloße Wort-Nachbarschaft (Komma, Zeilenumbruch, ...) ist KEIN Rubrum-Beleg
# (D12-Nachreview: sonst korroboriert "Rechtsanwalt Frank, Köln" fälschlich
# gegen ein Mandat "Frank ./. Köln"). Muster arbeiten auf dem Roh-Text (vor
# `tokenisiere()`), weil die Normalisierung Interpunktion wie "./." bereits
# entfernt.
_RUBRUM_MUSTER: tuple[re.Pattern[str], ...] = (
    re.compile(r"(\S+)\s*\./\.\s*(\S+)"),
    re.compile(r"(\S+)\s+gegen\s+(\S+)", re.IGNORECASE),
)


@dataclass
class ParteiTreffer:
    stufe: str        # "Z1" | "Z2" | "Z3" | "Z4"
    kategorie: str    # "treffer" | "moeglicher_treffer"
    score: float
    begruendung: str


def _z1_phrase(norm_name: str, norm_text: str) -> ParteiTreffer | None:
    if not norm_name or not norm_text:
        return None
    if f" {norm_name} " in f" {norm_text} ":
        return ParteiTreffer("Z1", STUFE_TREFFER, 1.0,
            f"Name '{norm_name}' als zusammenhängende Phrase im Text gefunden")
    return None


def _z2_token_menge(tokens_name: list[str], tokens_text: list[str]) -> ParteiTreffer | None:
    menge_name, menge_text = set(tokens_name), set(tokens_text)
    if not menge_name or not (menge_name <= menge_text):
        return None
    anzeige = ", ".join(sorted(menge_name))
    return ParteiTreffer("Z2", STUFE_TREFFER, 1.0,
        f"alle Namens-Tokens {{{anzeige}}} im Text enthalten (Wortreihenfolge unerheblich)")


def _z3_phonetik(tokens_name: list[str], tokens_text: list[str]) -> ParteiTreffer | None:
    if not tokens_name:
        return None
    codes_text = {c for c in (koelner_code(t) for t in tokens_text) if c}
    if not codes_text:
        return None
    treffer_codes: list[str] = []
    for t in tokens_name:
        c = koelner_code(t)
        if not c or c not in codes_text:
            return None
        treffer_codes.append(c)
    return ParteiTreffer("Z3", STUFE_MOEGLICH, 1.0,
        "alle Namens-Tokens phonetisch (Kölner Phonetik) im Text wiedergefunden: "
        f"[{', '.join(treffer_codes)}]")


def _z4_fuzzy(tokens_name: list[str], tokens_text: list[str],
              schwelle: float) -> ParteiTreffer | None:
    if not tokens_name or not tokens_text:
        return None
    einzelscores = [
        max(sequenz_ratio(t, u) for u in tokens_text) for t in tokens_name
    ]
    score = sum(einzelscores) / len(einzelscores)
    if score < schwelle:
        return None
    return ParteiTreffer("Z4", STUFE_MOEGLICH, round(score, 4),
        f"durchschnittliche Token-Ähnlichkeit {score:.2f} ≥ Schwelle {schwelle:.2f}")


def nachname(name: str) -> str:
    """Letztes normalisiertes Token eines Parteinamens = Nachname-Signal.

    Titel und Rechtsform-Zusätze sind durch `tokenisiere()` bereits
    gestrippt ("Dr. Petra Merkel" -> ["petra", "merkel"]). Einteilige Namen
    ergeben sich selbst. Leere Eingabe -> leerer String.

    Genutzt von `zuordnung.py` für die Stufe Z2N (Nachname + Korroboration);
    hier, weil dieses Modul die Normalisierungs-Bausteine ohnehin hält.

    # ponytail: nimmt die deutsche Reihenfolge "Vorname(n) Nachname" an —
    # bei "van der Berg"/"de Vries" ist das letzte Token nur der Kern des
    # Nachnamens. Für Z2N unschädlich (Kern-Token muss wörtlich im Text
    # stehen, ein zweites Signal korroboriert); bei Bedarf: Namensteil-Liste.
    """
    tokens = tokenisiere(name)
    return tokens[-1] if tokens else ""


def _rubrum_trenner_verbindet(text: str, nachname_token: str,
                               andere_nachnamen: set[str]) -> bool:
    """Steht `nachname_token` in `text` über einen expliziten Rubrum-Trenner
    (`_RUBRUM_MUSTER`, geschlossene Menge) unmittelbar neben einem der
    `andere_nachnamen`? Prüft auf dem Roh-Text, nicht auf Tokens — bloße
    Nachbarschaft ohne Trenner (Komma, Zeilenumbruch, ...) zählt nicht.

    # ponytail: geprüft wird nur das WORT direkt vor/nach dem Trenner, nicht
    # die volle (ggf. mehrwortige) Partei-Bezeichnung — "Merkel ./. Köhn"
    # trifft, "Frank ./. Sparkasse Köln" träfe nur, wenn `nachname_token`
    # zufällig "sparkasse" wäre. Für Z2N unschädlich: die schwächere
    # Nicht-Erkennung ist hier die sichere Richtung (Enthaltung statt
    # falschem Kandidaten). Bei Bedarf: Segment bis zum nächsten Trenner/
    # Satzende statt Einzelwort.
    """
    for muster in _RUBRUM_MUSTER:
        for m in muster.finditer(text):
            vor = tokenisiere(m.group(1))
            nach = tokenisiere(m.group(2))
            vor_nn = vor[-1] if vor else ""
            nach_nn = nach[0] if nach else ""
            if ((vor_nn == nachname_token and nach_nn in andere_nachnamen)
                    or (nach_nn == nachname_token and vor_nn in andere_nachnamen)):
                return True
    return False


def nachname_in_personen_position(nachname_token: str, text: str,
                                   andere_nachnamen: set[str]) -> bool:
    """Steht `nachname_token` in `text` an einer **Personen-Position**?

    Ein bloßes Vorkommen des letzten Namens-Tokens reicht für die Stufe Z2N
    nicht (siehe `zuordnung.py`): bei Organisationen ist das letzte Token
    kein Nachname, sondern oft ein Orts-/Gattungswort ("Stadtwerke Berlin"
    -> `berlin`), das im Text aus einem ganz anderen Grund steht
    ("Arbeitsgericht Berlin"). Ob ein Mandatsfeld eine natürliche Person
    meint, steht nirgends im Mandats-Schema — deshalb wird nicht der **Name**
    klassifiziert, sondern die **Fundstelle**: als Nachname zählt sie nur,
    wenn der Text sie wie eine Person adressiert. Zwei Muster:

      1. **Anrede davor**, wortgrenzen-genau — "Sehr geehrte Frau Dr.
         Merkel", "mit Herrn Köhn".
      2. **Rubrum** — durch einen expliziten Trenner aus der geschlossenen
         Menge `_RUBRUM_MUSTER` ("./.", " gegen ") mit dem Nachnamen der
         anderen Partei desselben Mandats verbunden ("Merkel ./. Köhn",
         "Frank gegen Köln").

    Bloße Wort-**Nachbarschaft** ohne einen dieser beiden Belege reicht
    NICHT (D12-Nachreview): "Rechtsanwalt Frank, Köln" korroboriert nicht
    gegen ein Mandat "Peter Frank" ./. "Sparkasse Köln" — hier steht "Köln"
    nur durch ein Komma getrennt neben "Frank", ohne Anrede und ohne
    Rubrum-Trenner. Alles andere zählt ebenfalls nicht (Enthaltung vor
    falschem Kandidaten): "… vor dem Arbeitsgericht Berlin …" belegt keinen
    Nachnamen.
    """
    if not nachname_token:
        return False
    tokens = tokenisiere(text)
    for i, token in enumerate(tokens):
        if token != nachname_token:
            continue
        davor = tokens[i - 1] if i else ""
        if davor in ANREDEN:
            return True
    return _rubrum_trenner_verbindet(text, nachname_token, andere_nachnamen)


def suche_name_in_text(name: str, text: str,
                        schwelle: float = SCHWELLE_MOEGLICH_DEFAULT) -> ParteiTreffer | None:
    """Prüft `name` gegen `text` in der Reihenfolge Z1 -> Z2 -> Z3 -> Z4;
    die erste zutreffende Stufe gewinnt. `None` = keine der Stufen trifft zu."""
    norm_name = normalisiere(name)
    norm_text = normalisiere(text)
    tokens_name = tokenisiere(name)
    tokens_text = tokenisiere(text)

    return (_z1_phrase(norm_name, norm_text)
            or _z2_token_menge(tokens_name, tokens_text)
            or _z3_phonetik(tokens_name, tokens_text)
            or _z4_fuzzy(tokens_name, tokens_text, schwelle))
