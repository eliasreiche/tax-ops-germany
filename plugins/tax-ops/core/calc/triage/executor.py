#!/usr/bin/env python3
"""triage — CLI-Executor (P2/P3): JSON-Eingabe rein, JSON-Report raus.

Wird vom Skill `aufgaben-triage` aufgerufen. Claude holt die Mails über
vorhandene M365-MCP-Server (kein Mail-Server-Zugriff hier, P4) und übergibt
sie als JSON; dieser Executor ordnet, priorisiert und schlägt Erledigungen
vor — alles regelbasiert (siehe `triage/rechner.py`). Anlegen/Austragen von
To-dos bestätigt der Mensch (P2); dieser Executor schreibt nirgends.

Eingabe (JSON-Datei):

    {"mails": [{"id","datum","von","betreff","text", "thread_id"?,
                "in_reply_to"?, "anhaenge"?: [...] }, ...],
     "mandanten": [{"name","kuerzel"?,"mandantennummer"?,"aliasse"?: [...]}]
                  ODER Pfad zu einer ";"-getrennten CSV
                  (Spalten: name;kuerzel;mandantennummer;aliasse, aliasse
                  mit "|" getrennt) — relativ zur Eingabedatei aufgelöst,
     "offene_aufgaben": [{"id","mandant","titel","angelegt",
                          "thread_id"?, "betreff"?}]?,
     "gesendet": [{"datum","an","betreff","thread_id"?,"in_reply_to"?}]?,
     "bundesland": "NW", "heute": "2026-09-08"}

CLI:
    python3 executor.py --input anfrage.json [--output report.json]

Exit-Codes (CONVENTIONS.md): 0 = Report erzeugt, 1 = fachlicher Fehler/
Schema-Verstoß, 2 = Eingabefehler (Datei fehlt, ungültiges JSON).
"""
from __future__ import annotations

import datetime as _dt
import sys
from email.utils import parseaddr
from pathlib import Path
from typing import Any

_CORE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(p) for p in (_CORE, _CORE / "calc") if str(p) not in sys.path]

from cli import CliFehler, lese_json_objekt, pflichtfeld, schreibe_report, standard_parser  # noqa: E402
from parteien import lese_csv_zeilen  # noqa: E402
from triage import (  # noqa: E402
    Mandant,
    TriageEingabeFehler,
    aufgabentitel_vorschlag,
    bewerte_mail,
    erkenne_indikatoren,
    extrahiere_bescheiddatum,
    extrahiere_steuernummern,
    finde_erledigt_vorschlaege,
    klassifiziere,
    zuordne_mandant,
)
from verify.provenienz import (  # noqa: E402
    STANDARD_TYPEN,
    STATUS_BELEGT,
    pruefe_provenienz,
    ws_collapse,
)

ERZEUGT_VON = "triage/executor.py"

TYPEN = {**STANDARD_TYPEN,
        "steuernummer": (lambda w: ws_collapse(w) or None, ws_collapse)}


def _liste(eingabe: dict[str, Any], feld: str) -> list[Any]:
    wert = eingabe.get(feld, [])
    if not isinstance(wert, list):
        raise TriageEingabeFehler(f"'{feld}' muss eine JSON-Liste sein, nicht {wert!r}")
    return wert


def _str_pflicht(eintrag: dict[str, Any], feld: str, ort: str) -> str:
    wert = eintrag.get(feld)
    if not isinstance(wert, str) or not wert.strip():
        raise TriageEingabeFehler(f"{ort}: Pflichtfeld '{feld}' fehlt oder ist leer")
    return wert


# --------------------------------------------------------------------------
# Mandanten (inline JSON-Liste oder CSV-Pfad, siehe parteien.py)
# --------------------------------------------------------------------------

def _mandanten_aus_csv(pfad: Path) -> list[Mandant]:
    _, zeilen = lese_csv_zeilen(pfad, TriageEingabeFehler)
    mandanten: list[Mandant] = []
    for i, zeile in enumerate(zeilen, start=2):
        name = zeile.get("name", "")
        if not name:
            raise TriageEingabeFehler(f"{pfad}, Zeile {i}: Pflichtfeld 'name' fehlt")
        aliasse = [a.strip() for a in zeile.get("aliasse", "").split("|") if a.strip()]
        mandanten.append(Mandant(
            name=name, kuerzel=zeile.get("kuerzel") or None,
            mandantennummer=zeile.get("mandantennummer") or None, aliasse=aliasse))
    return mandanten


def _mandanten_lesen(eingabe: dict[str, Any], input_pfad: Path) -> list[Mandant]:
    wert = eingabe.get("mandanten")
    if isinstance(wert, str):
        pfad = Path(wert)
        if not pfad.is_absolute():
            pfad = input_pfad.parent / pfad
        if not pfad.is_file():
            raise TriageEingabeFehler(f"Mandanten-CSV nicht gefunden: {pfad}")
        return _mandanten_aus_csv(pfad)
    if not isinstance(wert, list) or not wert:
        raise TriageEingabeFehler(
            "'mandanten' muss eine nicht-leere Liste oder ein CSV-Pfad (String) sein")
    mandanten = []
    for i, eintrag in enumerate(wert, start=1):
        if not isinstance(eintrag, dict):
            raise TriageEingabeFehler(f"mandanten[{i}]: kein JSON-Objekt")
        name = _str_pflicht(eintrag, "name", f"mandanten[{i}]")
        aliasse = eintrag.get("aliasse") or []
        if not isinstance(aliasse, list):
            raise TriageEingabeFehler(f"mandanten[{i}].aliasse muss eine Liste sein")
        mandanten.append(Mandant(
            name=name, kuerzel=eintrag.get("kuerzel"),
            mandantennummer=eintrag.get("mandantennummer"),
            aliasse=[str(a) for a in aliasse]))
    return mandanten


# --------------------------------------------------------------------------
# Provenienz — Bescheiddatum + Steuernummern gegen den Quelltext der Mail
# --------------------------------------------------------------------------

def _provenienz_geprueft(mail_id: str, betreff: str, text: str,
                         bescheiddatum: str | None,
                         steuernummern: list[str]) -> tuple[str | None, list[str]]:
    """Prüft die aus dem Mailtext extrahierten kritischen Werte gegen den
    Quelltext (P3). Da beide Extraktionen selbst aus `betreff`/`text`
    stammen, ist ein `nicht_belegt` hier ein Bug in der Extraktion, kein
    normaler Betriebszustand — der Wert wird trotzdem sicherheitshalber
    verworfen statt ungeprüft ausgegeben (Anti-Halluzination, P3)."""
    werte = []
    if bescheiddatum:
        werte.append({"pfad": f"mail:{mail_id}.bescheiddatum", "typ": "datum",
                      "wert": bescheiddatum})
    for i, sn in enumerate(steuernummern):
        werte.append({"pfad": f"mail:{mail_id}.steuernummer[{i}]", "typ": "steuernummer",
                      "wert": sn})
    if not werte:
        return bescheiddatum, steuernummern
    quellen = [(f"mail:{mail_id}:betreff", [betreff]), (f"mail:{mail_id}:text", [text])]
    ergebnisse = pruefe_provenienz(werte, quellen, TYPEN)
    belegte_sn = [r["wert"] for r in ergebnisse
                 if r["typ"] == "steuernummer" and r["status"] == STATUS_BELEGT]
    bescheiddatum_belegt = any(
        r["typ"] == "datum" and r["status"] == STATUS_BELEGT for r in ergebnisse)
    return (bescheiddatum if bescheiddatum_belegt else None), belegte_sn


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def _bewerte_eine_mail(mail: dict[str, Any], mandanten: list[Mandant],
                       bundesland: str, heute: _dt.date) -> dict[str, Any]:
    mail_id = _str_pflicht(mail, "id", "mails[]")
    betreff = str(mail.get("betreff") or "")
    text = str(mail.get("text") or "")
    von = str(mail.get("von") or "")
    von_name, von_adresse = parseaddr(von)
    von_name = von_name or von_adresse or von

    treffer = zuordne_mandant(von_name, von_adresse, betreff, text, mandanten)
    indikatoren = erkenne_indikatoren(betreff, text)
    klasse = klassifiziere(indikatoren, betreff, text)
    prioritaet, faelligkeit, unklar, kette = bewerte_mail(
        indikatoren, klasse, betreff, text, bundesland, heute)

    bescheiddatum_roh, _ = extrahiere_bescheiddatum(text)
    steuernummern_roh = extrahiere_steuernummern(f"{betreff} {text}")
    _, steuernummern = _provenienz_geprueft(
        mail_id, betreff, text, bescheiddatum_roh, steuernummern_roh)

    # Mehrdeutige Zuordnung (gemeinsamer Namensbestandteil) nennt keinen
    # Mandanten als zugeordnet, sondern nur die Kandidaten (P2: Mensch wählt).
    mehrdeutig = bool(treffer) and treffer[1].kategorie == "moeglicher_treffer"
    eintrag = {
        "mail_id": mail_id,
        "mandant": treffer[0].name if treffer and not mehrdeutig else None,
        "zuordnung_kandidaten": treffer[1].kandidaten if mehrdeutig else None,
        "zuordnung_stufe": treffer[1].stufe if treffer else None,
        "zuordnung_score": treffer[1].score if treffer else None,
        "zuordnung_begruendung": treffer[1].begruendung if treffer else None,
        "klasse_vorschlag": klasse,
        "indikatoren": [{"begriff": i["begriff"], "kategorie": i["kategorie"],
                         "norm": i["norm"], "fristart": i["fristart"],
                         "quelle_url": i["quelle_url"]} for i in indikatoren],
        "faelligkeit": faelligkeit,
        "faelligkeit_unklar": unklar,
        "prioritaet": prioritaet,
        "erkannte_steuernummern": steuernummern,
        "rechenkette": [s.as_dict() for s in kette],
        "aufgabentitel_vorschlag": aufgabentitel_vorschlag(indikatoren, betreff),
    }
    return eintrag


def baue_report(eingabe: dict[str, Any], input_pfad: Path) -> dict[str, Any]:
    mails = _liste(eingabe, "mails")
    if not mails:
        raise TriageEingabeFehler("'mails' ist leer — nichts zu priorisieren")
    bundesland = str(pflichtfeld(eingabe, "bundesland", fehler=TriageEingabeFehler))
    heute_roh = str(pflichtfeld(eingabe, "heute", fehler=TriageEingabeFehler))
    try:
        heute = _dt.date.fromisoformat(heute_roh)
    except ValueError:
        raise TriageEingabeFehler(f"'heute' ist kein gültiges ISO-Datum: {heute_roh!r}")

    mandanten = _mandanten_lesen(eingabe, input_pfad)
    offene_aufgaben = _liste(eingabe, "offene_aufgaben")
    gesendet = _liste(eingabe, "gesendet")

    vorschlaege = []
    unzugeordnet = []
    for i, mail in enumerate(mails, start=1):
        if not isinstance(mail, dict):
            raise TriageEingabeFehler(f"mails[{i}]: kein JSON-Objekt")
        eintrag = _bewerte_eine_mail(mail, mandanten, bundesland, heute)
        vorschlaege.append(eintrag)
        if eintrag["mandant"] is None:
            unzugeordnet.append({
                "mail_id": eintrag["mail_id"],
                "betreff": mail.get("betreff"),
                "von": mail.get("von"),
                "grund": ("mehrdeutig, Kandidaten: " + ", ".join(eintrag["zuordnung_kandidaten"])
                          if eintrag.get("zuordnung_kandidaten")
                          else "kein Mandant über der Zuordnungs-Schwelle"),
            })

    erledigt_vorschlaege = finde_erledigt_vorschlaege(offene_aufgaben, gesendet, mandanten)

    return {
        "meta": {
            "erzeugt_von": ERZEUGT_VON,
            "quelle_datei": str(input_pfad),
            "bundesland": bundesland,
            "heute": heute.isoformat(),
            "anzahl_mails": len(mails),
            "anzahl_mandanten": len(mandanten),
            "anzahl_offene_aufgaben": len(offene_aufgaben),
            "anzahl_gesendet": len(gesendet),
        },
        "vorschlaege": vorschlaege,
        "erledigt_vorschlaege": erledigt_vorschlaege,
        "unzugeordnet": unzugeordnet,
    }


def main(argv: list[str] | None = None) -> int:
    args = standard_parser(__doc__, "JSON-Eingabedatei (Posteingang-Triage-Anfrage)"
                           ).parse_args(argv)
    input_pfad = Path(args.input)
    try:
        eingabe = lese_json_objekt(input_pfad)
    except CliFehler as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    try:
        report = baue_report(eingabe, input_pfad)
    except (TriageEingabeFehler, ValueError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    try:
        schreibe_report(report, args.output)
    except CliFehler as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
