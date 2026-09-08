#!/usr/bin/env python3
"""Zweites Netz: sucht im Report nach Mustern, die auf Mandantendaten deuten.

Aufruf: python3 pruefe_report.py --datei report.md   (Exit 0 sauber, 1 Treffer, 2 Datei fehlt)
Nur Stdlib. Ein Regex-Netz fängt keine Firmennamen — dafür gilt die Whitelist in SKILL.md.
"""
import re
import sys

MUSTER = {
    "Steuernummer": r"\b\d{2,3}/\d{3}/\d{4,5}\b|\b\d{13}\b",
    "Steuer-IdNr.": r"\b\d{2}\s?\d{3}\s?\d{3}\s?\d{3}\b",
    "IBAN": r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}\b",
    "E-Mail": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "Telefon": r"(?:\+49|0)\s?\d{2,5}[\s/-]?\d{3,}",
    "Anrede/Name": r"\b(?:Herr|Frau|Familie|Eheleute)\s+[A-ZÄÖÜ][a-zäöüß-]+",
    "Firma": r"\b[A-ZÄÖÜ][\wäöüß&.\- ]{1,40}\s(?:GmbH|AG|KG|OHG|UG|e\.\s?K\.|GbR|mbH|PartG|SE)\b",
    "Aktenzeichen": r"\b(?:Az\.?|Aktenzeichen|St\.?-?Nr\.?|Mandant(?:en)?-?Nr\.?)\s*:?\s*\S+",
}
ERLAUBT = re.compile(r"elias@law-flow\.de|\[(?:Mandant|Steuernummer|Betrag)\]")


def pruefe(text: str) -> list[tuple[int, str, str]]:
    treffer = []
    for nr, zeile in enumerate(text.splitlines(), 1):
        bereinigt = ERLAUBT.sub("", zeile)
        for name, muster in MUSTER.items():
            for m in re.finditer(muster, bereinigt):
                treffer.append((nr, name, m.group(0)))
    return treffer


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "--datei":
        print("Aufruf: pruefe_report.py --datei <report.md>", file=sys.stderr)
        return 2
    try:
        text = open(sys.argv[2], encoding="utf-8").read()
    except OSError as e:
        print(f"Datei nicht lesbar: {e}", file=sys.stderr)
        return 2
    t = pruefe(text)
    for nr, name, wert in t:
        print(f"Zeile {nr}: {name}: {wert!r}")
    print("sauber" if not t else f"{len(t)} Treffer — entfernen oder Platzhalter setzen")
    return 1 if t else 0


def demo() -> None:
    schmutzig = ("Skill: ao-fristenrechner\nMandant: Backstube Sonnenschein GmbH\n"
                 "Steuernummer 12/345/67890, Kontakt info@backstube.example, Herr Meier")
    arten = {name for _, name, _ in pruefe(schmutzig)}
    assert {"Firma", "Steuernummer", "E-Mail", "Anrede/Name"} <= arten, arten
    sauber = ("Skill: ao-fristenrechner\naufgabe_zur_post: 2026-02-03, bundesland: NW\n"
              "Ergebnis: 2026-03-09, erwartet: 2026-03-06\nAn: elias@law-flow.de\nMandant: [Mandant]")
    assert pruefe(sauber) == [], pruefe(sauber)
    print("demo ok")


if __name__ == "__main__":
    sys.exit(demo() or 0 if "--demo" in sys.argv else main())
