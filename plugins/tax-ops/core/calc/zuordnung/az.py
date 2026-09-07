"""zuordnung.az — Aktenzeichen-Normalisierung und -Suche (P3-Bibliothek).

Stufe Z0 der E-Mail-Akten-Zuordnung (siehe `zuordnung.py`, sicherste Stufe):
Das eigene Aktenzeichen eines Mandats kommt wörtlich (nach Normalisierung)
im Betreff oder Textauszug einer E-Mail vor.

## Normalisierung

Mehrfach-Whitespace wird zu einem einzigen Leerzeichen kollabiert,
führende/folgende Leerzeichen entfernt. Groß-/Kleinschreibung bleibt
erhalten — Aktenzeichen sind i. d. R. schreibweisentreu (z. B. "2026-001",
"12 O 345/26 K01").

Bewusst **kein** Wortgrenzen-Check (`\\b`) beim Substring-Vergleich:
Aktenzeichen enthalten häufig eigene Trennzeichen (`/`, `-`, Leerzeichen),
die faktisch bereits Wortgrenzen bilden; ein zusätzlicher `\\b`-Check
würde Aktenzeichen an ihrem Rand (z. B. direkt gefolgt von Interpunktion
wie "2026-001," oder eingebettet wie "(2026-001)") verpassen.

## Wiederverwendungs-Entscheidung (Az-Regex)

`plugins/legal-ops/skills/aktenkopf-extraktor/executor.py` normalisiert
Aktenzeichen für seinen Provenienz-Abgleich bereits mit demselben Muster
(dortige `_kanon_ziel(wert, "aktenzeichen")` → `_ws_collapse`: Whitespace
kollabieren). Diese Funktion wird hier **bewusst nicht importiert**,
sondern eigenständig nachgebildet: `core/calc/` darf nicht von
`plugins/legal-ops/skills/*` abhängen (umgekehrte Abhängigkeitsrichtung,
siehe `core/calc/README.md` — Rechner liegen unterhalb der Skills, nie
umgekehrt) und `_ws_collapse` ist dort eine private, nicht für
Fremdnutzung vorgesehene Modulfunktion eines Skill-Executors, kein Teil
einer wiederverwendbaren Bibliothek. Das Muster selbst (Whitespace-
Kollabierung) ist mit zwei Codezeilen trivial und wird hier 1:1
übernommen — siehe Abschlussbericht der Implementierung für die
Begründung dieser Entscheidung.
"""
from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")


def normalisiere_az(wert: str) -> str:
    """Kollabiert Mehrfach-Whitespace zu einem Leerzeichen, trimmt Ränder.

    Leere/`None`-Eingaben ergeben einen leeren String.
    """
    if not wert:
        return ""
    return _WHITESPACE_RE.sub(" ", wert).strip()


def az_gefunden_in_text(az: str, text: str) -> bool:
    """True, wenn das normalisierte `az` als Teilstring im normalisierten `text` vorkommt.

    Ein leeres `az` ergibt nie einen Treffer (kein Aktenzeichen ist kein
    Freibrief für "trifft auf alles zu") — ebenso ein leerer `text`.
    """
    az_norm = normalisiere_az(az)
    if not az_norm:
        return False
    return az_norm in normalisiere_az(text)
