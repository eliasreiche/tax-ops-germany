#!/usr/bin/env python3
"""triage — deterministische Posteingang-Priorisierung (P2/P3).

Baut aus einem Mail-Posteingang (bereits als JSON übergeben, kein Live-
Mail-Zugriff hier — P4, siehe SKILL.md) eine Vorschlagsliste: Mandanten-
Zuordnung, Fristindikatoren, Priorität und "vermutlich erledigt"-Hinweise
für offene Aufgaben. Alles hier ist regelbasiert; die Feinklassifikation in
natürlicher Sprache (Aufgabentitel-Formulierung) ist Sache von Claude im
Skill-Prompt (SKILL.md) — dieser Rechner liefert nur den regelbasierten
Rohvorschlag (CONVENTIONS.md, `stberg_einordnung`: organisatorisch, keine
Hilfeleistung).

## Bausteine

1. **Mandanten-Zuordnung** (`zuordne_mandant`) — Domain/Mandantennummer
   (literal, `treffer`) vor Name/Alias (`core/calc/matching`, Stufen S1-S4,
   gegen Absender-Name UND Betreff). Kein Treffer über der Schwelle oder ein
   Gleichstand zwischen zwei Mandanten -> `unzugeordnet` (nie geraten).
2. **Fristindikatoren** (`erkenne_indikatoren`) — Substring-Suche gegen
   `indikatoren.json`, längster Begriff zuerst (vermeidet, dass ein
   generischer Begriff wie "bescheid" einen spezifischeren wie
   "vorauszahlungsbescheid" verdeckt oder umgekehrt fälschlich beide feuern).
3. **Bescheiddatum -> Fälligkeit** (`extrahiere_bescheiddatum`,
   `berechne_bescheid_faelligkeit`) — nur für die Kategorie
   `bescheid_einspruch`: sucht ein Datum im Umfeld der Label "Bescheid vom"/
   "Datum" und reicht es an `core/calc/ao_fristen` weiter (Einspruchsfrist).
   **Bewusste Annahme**: das Bescheiddatum wird als Datum der Aufgabe zur
   Post behandelt (§ 122 Abs. 2 Nr. 1 AO) — in der Praxis meist zutreffend,
   aber nicht zwingend; ein bestätigtes Zustelldatum geht vor, sofern
   bekannt (siehe SKILL.md "Nicht abgedeckt").
4. **Priorität** (`prioritaet_und_kette`) — Matrix aus Indikator-
   Standard-Dringlichkeit und Restfrist (Werktage bis Fälligkeit), als
   `RechenSchritt`-Kette.
5. **Erledigt-Vorschlag** (`finde_erledigt_vorschlaege`) — offene Aufgabe
   gilt als vermutlich erledigt, wenn eine gesendete Mail an denselben
   Mandanten per `thread_id`/`in_reply_to` oder normalisiertem Betreff
   nach `angelegt` verknüpft ist. Nur Vorschlag mit Beleg, kein Austragen.

Nur Standardbibliothek. Kein Netzwerkzugriff, keine Persistierung.
"""
from __future__ import annotations

import json
import re
import sys
import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_CALC_DIR = Path(__file__).resolve().parents[1]
if str(_CALC_DIR) not in sys.path:
    sys.path.insert(0, str(_CALC_DIR))

from ao_fristen.rechner import (  # noqa: E402
    AONichtAbgedeckt,
    berechne_einspruchsfrist,
)
from datum import kanons_in_zeile  # noqa: E402
from matching import STUFE_MOEGLICH, STUFE_TREFFER, vergleiche_namen  # noqa: E402
from rechenschritt import RechenSchritt  # noqa: E402

_HIER = Path(__file__).resolve().parent
INDIKATOREN_PFAD = _HIER / "indikatoren.json"

SCHWELLE_MOEGLICH_DEFAULT = 0.85

STUFE_DOMAIN = "domain"
STUFE_MANDANTENNUMMER = "mandantennummer"
# Reihenfolge: exakte Identifikatoren (Domain/Mandantennummer) vor den
# gestuften Namensvergleichen S1-S4 (core/calc/matching) — ein Bezug über
# eine eindeutige Kennung ist sicherer als jeder Namensabgleich.
_STUFE_ORDNUNG = {STUFE_DOMAIN: 0, STUFE_MANDANTENNUMMER: 0,
                  "S1": 1, "S2": 2, "S3": 3, "S4": 4}

_WHITESPACE_RE = re.compile(r"\s+")
_STEUERNUMMER_RE = re.compile(r"\b\d{2,3}/\d{3}/\d{4,5}\b")
_LABEL_DATUM_RE = re.compile(r"(?:bescheid\s+vom|datum)\s*:?\s*", re.IGNORECASE)
_ANTWORT_PREFIX_RE = re.compile(r"^(?:re|aw|wg)\s*:\s*", re.IGNORECASE)

_DRINGLICHKEIT_RANG = {"info": 0, "normal": 1, "hoch": 2, "sofort": 3}
PRIORITAETEN = tuple(_DRINGLICHKEIT_RANG)  # ("info", "normal", "hoch", "sofort")

NEWSLETTER_MUSTER = ("newsletter", "rundschreiben", "informationsschreiben",
                     "zur kenntnisnahme", "zur information")


class TriageEingabeFehler(ValueError):
    """Fachlicher Fehler/Schema-Verstoß der Eingabe → Exit 1 (CONVENTIONS.md)."""


@dataclass
class Mandant:
    name: str
    kuerzel: str | None = None
    mandantennummer: str | None = None
    aliasse: list[str] = field(default_factory=list)


@dataclass
class ZuordnungTreffer:
    stufe: str        # "domain" | "mandantennummer" | "S1".."S4"
    kategorie: str    # "treffer" | "moeglicher_treffer"
    score: float
    begruendung: str


def _ws_kanon(wert: str) -> str:
    return _WHITESPACE_RE.sub(" ", wert or "").strip()


def _domain(adresse: str) -> str:
    return adresse.rsplit("@", 1)[-1].strip().lower() if "@" in (adresse or "") else ""


# --------------------------------------------------------------------------
# 1. Mandanten-Zuordnung
# --------------------------------------------------------------------------

def _domain_treffer(mandant: Mandant, von_adresse: str) -> ZuordnungTreffer | None:
    domain = _domain(von_adresse)
    if not domain:
        return None
    for alias in mandant.aliasse:
        alias_norm = alias.strip().lower().lstrip("@")
        if alias_norm and "." in alias_norm and alias_norm == domain:
            return ZuordnungTreffer(
                STUFE_DOMAIN, STUFE_TREFFER, 1.0,
                f"Absender-Domain '{domain}' == Alias '{alias}' von Mandant '{mandant.name}'")
    return None


def _mandantennummer_treffer(mandant: Mandant, betreff: str, text: str) -> ZuordnungTreffer | None:
    if not mandant.mandantennummer:
        return None
    nummer = _ws_kanon(mandant.mandantennummer)
    if not nummer:
        return None
    heuhaufen = _ws_kanon(f"{betreff} {text}")
    if nummer in heuhaufen:
        return ZuordnungTreffer(
            STUFE_MANDANTENNUMMER, STUFE_TREFFER, 1.0,
            f"Mandantennummer '{nummer}' wörtlich in Betreff/Text gefunden")
    return None


def _bester_namens_treffer(mandant: Mandant, von_name: str, betreff: str,
                           schwelle: float) -> ZuordnungTreffer | None:
    """Vergleicht Name + Aliasse gegen Absender-Name und Betreff über
    `matching.vergleiche_namen` (S1-S4); liefert den besten Treffer. Ein
    Betreff ist Fließtext, keine kurze Namensangabe — S2 (Token-Teilmenge)
    fängt den typischen Fall ("Re: Unterlagen Müller GmbH" enthält alle
    Namens-Tokens von "Müller GmbH" als Teilmenge)."""
    kandidaten: list[tuple[str, str, Any]] = []
    for name in [mandant.name, *mandant.aliasse]:
        if not name:
            continue
        for feldname, feldtext in (("absender_name", von_name), ("betreff", betreff)):
            if not feldtext:
                continue
            treffer = vergleiche_namen(name, feldtext, schwelle)
            if treffer is not None:
                kandidaten.append((feldname, name, treffer))
    if not kandidaten:
        return None
    feldname, name, treffer = min(
        kandidaten, key=lambda k: (_STUFE_ORDNUNG[k[2].regel], -k[2].score))
    return ZuordnungTreffer(
        treffer.regel, treffer.stufe, treffer.score,
        f"'{name}' vs. Feld '{feldname}': {treffer.begruendung}")


def zuordne_mandant(von_name: str, von_adresse: str, betreff: str, text: str,
                    mandanten: list[Mandant],
                    schwelle: float = SCHWELLE_MOEGLICH_DEFAULT
                    ) -> tuple[Mandant, ZuordnungTreffer] | None:
    """Bester Mandanten-Treffer für ein Dokument (Mail oder gesendete Mail),
    oder `None` — entweder weil kein Mandant über der Schwelle liegt, oder
    weil zwei Mandanten auf derselben besten Stufe gleichauf liegen
    (Enthaltung statt Raten, wie Z2N in `core/calc/zuordnung`)."""
    treffer_je_mandant: list[tuple[Mandant, ZuordnungTreffer]] = []
    for mandant in mandanten:
        treffer = (_domain_treffer(mandant, von_adresse)
                  or _mandantennummer_treffer(mandant, betreff, text)
                  or _bester_namens_treffer(mandant, von_name, betreff, schwelle))
        if treffer is not None:
            treffer_je_mandant.append((mandant, treffer))
    if not treffer_je_mandant:
        return None

    def sortkey(mt: tuple[Mandant, ZuordnungTreffer]):
        _, t = mt
        return (0 if t.kategorie == STUFE_TREFFER else 1, _STUFE_ORDNUNG[t.stufe], -t.score)

    treffer_je_mandant.sort(key=sortkey)
    bester, zweitbester = treffer_je_mandant[0], (
        treffer_je_mandant[1] if len(treffer_je_mandant) > 1 else None)
    if zweitbester is not None and sortkey(bester) == sortkey(zweitbester):
        return None  # Gleichstand -> Enthaltung, nie geraten
    return bester


# --------------------------------------------------------------------------
# 2. Fristindikatoren
# --------------------------------------------------------------------------

def lade_indikatoren() -> list[dict[str, Any]]:
    daten = json.loads(INDIKATOREN_PFAD.read_text(encoding="utf-8"))
    return daten["indikatoren"]


def erkenne_indikatoren(betreff: str, text: str,
                        katalog: list[dict[str, Any]] | None = None
                        ) -> list[dict[str, Any]]:
    """Höchstens ein Treffer je Kategorie, längster Begriff zuerst. Ein
    kürzerer Begriff, der nur als Teilstring eines bereits akzeptierten
    LÄNGEREN Begriffs vorkommt (z. B. "bescheid" in "vorauszahlungsbescheid"),
    zählt nicht als eigener Treffer einer ANDEREN Kategorie — sonst würde ein
    Vorauszahlungsbescheid zusätzlich fälschlich als generischer
    Steuerbescheid (Kategorie `bescheid_einspruch`) samt Einspruchsfrist-
    Berechnung einsortiert."""
    katalog = katalog if katalog is not None else lade_indikatoren()
    heuhaufen = f"{betreff} {text}".lower()
    gesehen_kategorien: set[str] = set()
    akzeptierte_begriffe: list[str] = []
    treffer: list[dict[str, Any]] = []
    for zeile in sorted(katalog, key=lambda z: -len(z["begriff"])):
        begriff = zeile["begriff"].lower()
        if begriff not in heuhaufen or zeile["kategorie"] in gesehen_kategorien:
            continue
        if any(begriff in laenger for laenger in akzeptierte_begriffe):
            continue
        treffer.append(zeile)
        gesehen_kategorien.add(zeile["kategorie"])
        akzeptierte_begriffe.append(begriff)
    return treffer


# --------------------------------------------------------------------------
# 3. Bescheiddatum -> Fälligkeit
# --------------------------------------------------------------------------

def extrahiere_bescheiddatum(text: str, fenster: int = 20) -> tuple[str | None, bool]:
    """(iso_datum, mehrdeutig) — sucht Label "Bescheid vom"/"Datum" und ein
    Datum in den `fenster` Zeichen danach. `mehrdeutig=True`, wenn ein
    Label-Fenster mehrere Datumskandidaten enthält oder mehrere
    Label-Fundstellen auf unterschiedliche Daten zeigen — dann wird NIE
    geraten (Anti-Halluzination), sondern `[unklar]` an den Aufrufer
    zurückgemeldet."""
    kandidaten: set[str] = set()
    gefunden_label = False
    for m in _LABEL_DATUM_RE.finditer(text):
        gefunden_label = True
        ausschnitt = text[m.end(): m.end() + fenster]
        treffer = kanons_in_zeile(ausschnitt)
        if len(treffer) > 1:
            return None, True
        kandidaten |= treffer
    if not gefunden_label or not kandidaten:
        return None, False
    if len(kandidaten) > 1:
        return None, True
    return next(iter(kandidaten)), False


def extrahiere_steuernummern(text: str) -> list[str]:
    return sorted(set(_STEUERNUMMER_RE.findall(text or "")))


def berechne_bescheid_faelligkeit(bescheiddatum_iso: str, bundesland: str):
    """Reicht das Bescheiddatum als Datum der Aufgabe zur Post an
    `core/calc/ao_fristen` weiter (§ 122 Abs. 2 Nr. 1 AO) — siehe
    Modul-Docstring, bewusste Annahme. Wirft `AONichtAbgedeckt` z. B. bei
    einem Datum vor 2025-01-01 (unverändert aus ao_fristen)."""
    datum = _dt.date.fromisoformat(bescheiddatum_iso)
    return berechne_einspruchsfrist(bundesland=bundesland, aufgabe_zur_post_datum=datum)


# --------------------------------------------------------------------------
# 4. Priorität
# --------------------------------------------------------------------------

def _werktage_bis(heute: _dt.date, ziel: _dt.date) -> int:
    """Anzahl Werktage (Mo-Fr) von `heute` (exklusiv) bis `ziel` (inklusiv).
    Negativ, wenn `ziel` vor `heute` liegt (bereits überfällig).

    # ponytail: zählt Kalender-Werktage ohne Feiertage — für die grobe
    # Dringlichkeits-Einstufung ausreichend (die exakte Fristberechnung
    # inkl. Feiertagen läuft ohnehin über core/calc/ao_fristen); bei Bedarf:
    # core/calc/feiertage einbeziehen.
    """
    if ziel < heute:
        return -((heute - ziel).days)
    tage = 0
    d = heute
    while d < ziel:
        d += _dt.timedelta(days=1)
        if d.weekday() < 5:
            tage += 1
    return tage


def _dringlichkeit_aus_restfrist(werktage: int) -> str:
    if werktage < 3:
        return "sofort"
    if werktage <= 10:
        return "hoch"
    return "normal"


def klassifiziere(indikatoren: list[dict[str, Any]], betreff: str, text: str) -> str:
    """Regelbasierte Grobklassifikation (`aufgabe`/`info`/`rueckfrage`/
    `unklar`) — nur die Vorstufe; Feinklassifikation und Aufgabentitel in
    natürlicher Sprache sind Sache von Claude im Skill-Prompt."""
    if indikatoren:
        return "aufgabe"
    heuhaufen = f"{betreff} {text}".lower()
    if any(m in heuhaufen for m in NEWSLETTER_MUSTER):
        return "info"
    if "?" in (betreff or "") or "?" in (text or ""):
        return "rueckfrage"
    return "unklar"


def bescheid_faelligkeit_und_kette(bescheiddatum: str | None, mehrdeutig: bool,
                                   bundesland: str, heute: _dt.date, kette: list[RechenSchritt],
                                   standard_dringlichkeit: str
                                   ) -> tuple[str, str | None, bool]:
    """Hängt die Bescheiddatum-/Fälligkeits-/Restfrist-Schritte an `kette`
    an (in-place) und liefert (prioritaet, faelligkeit_iso, unklar)."""
    if mehrdeutig:
        kette.append(RechenSchritt(
            len(kette) + 1, "Textanalyse",
            "Mehrere/mehrdeutige Datumsangaben im Umfeld von 'Bescheid vom'/'Datum' "
            "gefunden — kein Datum wird geraten.", "[unklar]"))
        kette.append(RechenSchritt(
            len(kette) + 1, "Regel",
            "Mehrdeutiges Bescheiddatum -> Priorität zwingend 'hoch' (Zweitkontrolle).",
            "hoch"))
        return "hoch", None, True

    if not bescheiddatum:
        kette.append(RechenSchritt(
            len(kette) + 1, "Textanalyse",
            "Kein Bescheiddatum im Umfeld von 'Bescheid vom'/'Datum' gefunden — "
            "nur Hinweis, keine Fälligkeitsberechnung.", None))
        kette.append(RechenSchritt(
            len(kette) + 1, "Prioritäts-Matrix",
            f"Kein Fälligkeitsdatum -> Standard-Dringlichkeit "
            f"'{standard_dringlichkeit}' übernommen.", standard_dringlichkeit))
        return standard_dringlichkeit, None, False

    kette.append(RechenSchritt(
        len(kette) + 1, "Textanalyse",
        f"Bescheiddatum im Text erkannt: {bescheiddatum}.", bescheiddatum))

    try:
        ergebnis = berechne_bescheid_faelligkeit(bescheiddatum, bundesland)
    except AONichtAbgedeckt as exc:
        kette.append(RechenSchritt(
            len(kette) + 1, "ao_fristen", f"Fälligkeit nicht berechenbar: {exc}", None))
        return standard_dringlichkeit, None, False

    for schritt in ergebnis.rechenkette:
        kette.append(RechenSchritt(
            len(kette) + 1, schritt.norm, schritt.beschreibung, schritt.ergebnis))

    faelligkeit = ergebnis.fristende
    werktage = _werktage_bis(heute, faelligkeit)
    restfrist_dringlichkeit = _dringlichkeit_aus_restfrist(werktage)
    kette.append(RechenSchritt(
        len(kette) + 1, "Dringlichkeits-Einstufung",
        f"Restfrist heute ({heute.isoformat()}) -> Fälligkeit ({faelligkeit.isoformat()}): "
        f"{werktage} Werktage.", restfrist_dringlichkeit))

    final_rang = max(_DRINGLICHKEIT_RANG[standard_dringlichkeit],
                     _DRINGLICHKEIT_RANG[restfrist_dringlichkeit])
    prioritaet = PRIORITAETEN[final_rang]
    kette.append(RechenSchritt(
        len(kette) + 1, "Prioritäts-Matrix",
        f"max(Indikator-Dringlichkeit='{standard_dringlichkeit}', "
        f"Restfrist-Dringlichkeit='{restfrist_dringlichkeit}') = '{prioritaet}'.",
        prioritaet))
    return prioritaet, faelligkeit.isoformat(), False


def bewerte_mail(indikatoren: list[dict[str, Any]], klasse: str, betreff: str, text: str,
                 bundesland: str, heute: _dt.date
                 ) -> tuple[str, str | None, bool, list[RechenSchritt]]:
    """Öffentliche Haupt-API für Baustein 3+4 zusammen: baut die vollständige
    Rechenkette (Indikatoren -> ggf. Bescheiddatum/Fälligkeit -> Priorität)."""
    kette: list[RechenSchritt] = []
    if not indikatoren:
        prioritaet = "info" if klasse == "info" else "normal"
        kette.append(RechenSchritt(1, "Regel", "Kein Fristindikator erkannt.", prioritaet))
        return prioritaet, None, False, kette

    for ind in indikatoren:
        kette.append(RechenSchritt(
            len(kette) + 1, ind["norm"],
            f"Indikator '{ind['begriff']}' erkannt (Kategorie: {ind['kategorie']}, "
            f"Standard-Dringlichkeit: {ind['standard_dringlichkeit']}).", None))

    bescheid = next((i for i in indikatoren if i["kategorie"] == "bescheid_einspruch"), None)
    bester_rang = max(_DRINGLICHKEIT_RANG[i["standard_dringlichkeit"]] for i in indikatoren)

    if bescheid is None:
        prioritaet = PRIORITAETEN[bester_rang]
        kette.append(RechenSchritt(
            len(kette) + 1, "Prioritäts-Matrix",
            f"Keine Fälligkeitsberechnung für diese Kategorie(n) — höchste "
            f"Standard-Dringlichkeit '{prioritaet}' übernommen.", prioritaet))
        return prioritaet, None, False, kette

    bescheiddatum, mehrdeutig = extrahiere_bescheiddatum(text)
    prioritaet, faelligkeit, unklar = bescheid_faelligkeit_und_kette(
        bescheiddatum, mehrdeutig, bundesland, heute, kette,
        bescheid["standard_dringlichkeit"])

    if len(indikatoren) > 1:
        # weitere Indikatoren neben dem Bescheid tragen ihre eigene
        # Standard-Dringlichkeit bei (z. B. Bescheid + Mahnung in einer Mail).
        andere_rang = max(_DRINGLICHKEIT_RANG[i["standard_dringlichkeit"]]
                          for i in indikatoren if i is not bescheid)
        gesamt_rang = max(_DRINGLICHKEIT_RANG[prioritaet], andere_rang)
        if PRIORITAETEN[gesamt_rang] != prioritaet:
            prioritaet = PRIORITAETEN[gesamt_rang]
            kette.append(RechenSchritt(
                len(kette) + 1, "Prioritäts-Matrix",
                f"Weiterer Indikator mit höherer Standard-Dringlichkeit -> "
                f"Priorität angehoben auf '{prioritaet}'.", prioritaet))

    return prioritaet, faelligkeit, unklar, kette


# --------------------------------------------------------------------------
# Aufgabentitel (grober, regelbasierter Vorschlag — Feinschliff bei Claude)
# --------------------------------------------------------------------------

def aufgabentitel_vorschlag(indikatoren: list[dict[str, Any]], betreff: str) -> str:
    betreff_anzeige = (betreff or "").strip() or "(ohne Betreff)"
    if not indikatoren:
        return betreff_anzeige
    kategorie = indikatoren[0]["kategorie"].replace("_", " ")
    return f"{kategorie}: {betreff_anzeige}"


# --------------------------------------------------------------------------
# 5. Erledigt-Vorschlag
# --------------------------------------------------------------------------

def normalisiere_betreff(betreff: str) -> str:
    """Entfernt beliebig viele führende Re:/AW:/WG:-Präfixe, dann
    Whitespace-Kollabierung + Kleinschreibung."""
    b = (betreff or "").strip()
    while True:
        neu = _ANTWORT_PREFIX_RE.sub("", b).strip()
        if neu == b:
            break
        b = neu
    return _ws_kanon(b).lower()


def _match_art(aufgabe: dict[str, Any], gesendet: dict[str, Any]) -> str | None:
    aufgabe_thread = aufgabe.get("thread_id")
    if aufgabe_thread and gesendet.get("thread_id") == aufgabe_thread:
        return "thread_id"
    if aufgabe_thread and gesendet.get("in_reply_to") == aufgabe_thread:
        return "in_reply_to"
    aufgabe_betreff = aufgabe.get("betreff")
    if aufgabe_betreff and gesendet.get("betreff") and (
            normalisiere_betreff(aufgabe_betreff) == normalisiere_betreff(gesendet["betreff"])):
        return "betreff_normalisiert"
    return None


def finde_erledigt_vorschlaege(offene_aufgaben: list[dict[str, Any]],
                               gesendet: list[dict[str, Any]],
                               mandanten: list[Mandant],
                               schwelle: float = SCHWELLE_MOEGLICH_DEFAULT
                               ) -> list[dict[str, Any]]:
    """Ein Vorschlag je Aufgabe (der erste passende Beleg reicht) — nur mit
    Beleg, kein automatisches Austragen (P2, siehe Modul-Docstring)."""
    vorschlaege: list[dict[str, Any]] = []
    for aufgabe in offene_aufgaben:
        for g in gesendet:
            art = _match_art(aufgabe, g)
            if art is None:
                continue
            if not (g.get("datum") and aufgabe.get("angelegt")
                    and g["datum"] > aufgabe["angelegt"]):
                continue
            treffer = zuordne_mandant(g.get("an", ""), g.get("an", ""), g.get("betreff", ""),
                                      "", mandanten, schwelle)
            if treffer is None or treffer[0].name != aufgabe.get("mandant"):
                continue
            vorschlaege.append({
                "aufgabe_id": aufgabe.get("id"),
                "mandant": aufgabe.get("mandant"),
                "titel": aufgabe.get("titel"),
                "match_art": art,
                "beleg": {
                    "an": g.get("an"),
                    "datum": g.get("datum"),
                    "betreff": g.get("betreff"),
                },
            })
            break
    return vorschlaege
