"""zuordnung.zuordnung — Dokument-Metadaten -> Mandats-Kandidaten (P2/P3-Bibliothek).

Öffentliche Haupt-API von `core/calc/zuordnung/`, genutzt vom Skill
`email-akten-zuordnung/executor.py` und später (D-Vorgabe) vom Skill #14
`posteingang-ocr-verteilung` — deshalb bewusst klein gehaltene Signatur
(siehe `finde_kandidaten()`).

## Stufen-Übersicht

    Z0  eigenes Aktenzeichen wörtlich (nach Az-Normalisierung, siehe `az.py`)
        in Betreff **oder** Textauszug                          -> treffer
    Z1-Z4  Parteiname (`mandant`/`gegenseite`) gegen Betreff,
        Textauszug oder Absendername (siehe `parteisuche.py`)    -> treffer (Z1/Z2)
                                                                    moeglicher_treffer (Z3/Z4)
    Z2N  **Nachname + Korroboration** — die Nachnamen ZWEIER Beteiligter
        desselben Mandats (`mandant` UND `gegenseite`) stehen je wörtlich
        (keine Phonetik/Fuzzy) UND in Personen-Position (Anrede davor
        oder expliziter Rubrum-Trenner "./."/" gegen ") im Dokument
                                                                -> moeglicher_treffer

## Warum Z2N (Nachname + Korroboration)

Z1/Z2 verlangen den **vollständigen** `mandant`/`gegenseite`-String. Eigene
Kanzleikorrespondenz redet aber mit "Sehr geehrte Frau Dr. Merkel" — der
Vorname fehlt, Z2 scheitert an einem einzigen Token, sachlich eindeutige
Post landet als `kein_treffer` (Pilot-Abnahme 2026-08, 2 von 6 Mails).

Z2N schließt diese Lücke bewusst eng:

  - Ein Nachname allein reicht NIE — es braucht ein zweites, wörtlich
    belegtes Nachname-Signal aus demselben Mandat. Damit bleibt Z2N ohne
    neue Datenpflege: es nutzt nur die Felder, die `Mandat` ohnehin trägt.
  - Ein Vorkommen des letzten Namens-Tokens allein ist noch kein
    Nachname-Signal: es muss in **Personen-Position** stehen (Anrede davor
    ODER ein expliziter Rubrum-Trenner aus einer geschlossenen Menge
    ("./.", " gegen ") unmittelbar neben dem Nachnamen der anderen Partei —
    siehe `parteisuche.nachname_in_personen_position()`). Bloße
    Wort-Nachbarschaft OHNE Anrede/Trenner reicht NICHT (D12-Nachreview:
    sonst korroboriert "Rechtsanwalt Frank, Köln" fälschlich gegen ein
    Mandat "Frank" ./. "Köln" — ein Komma ist kein Trenner). Ebenso
    korroboriert bei einer Organisations-Gegenseite deren Orts-/Gattungstoken
    ("Stadtwerke Berlin" -> `berlin`) nicht einfach durch Nachbarschaft einen
    Fundort, der nichts mit dem Mandat zu tun hat ("Arbeitsgericht Berlin").
    Ob ein Mandatsfeld eine natürliche Person meint, sagt das Mandats-Schema
    nicht (`az`/`mandant`/`gegenseite`, kein `typ`-Feld wie in
    `interessenkollision-check`) — geprüft wird deshalb die Fundstelle,
    nicht der Name.
  - Ein Mandat ohne `gegenseite` erreicht Z2N nie (keine Korroborations-
    quelle) — Einzelnamen-Post bleibt `kein_treffer` statt geraten.
  - Kategorie ist immer `moeglicher_treffer`: ein Nachname ist schwächere
    Evidenz als ein Vollname (Z1/Z2) und weit schwächer als ein Az (Z0),
    also nie ein `treffer`. Die Ablage bleibt Kanzlei-Bestätigung.
  - Trifft dasselbe Nachname-Signal auf mehrere Z2N-fähige Mandate zu, wird
    für ALLE betroffenen Mandate KEIN Kandidat erzeugt (Enthaltung); der
    Grund steht als Hinweis in `finde_kandidaten_mit_hinweisen()`.

Z0 wird IMMER zuerst geprüft (sicherste Stufe) — findet sich das eigene
Az, wird kein Parteiname-Abgleich mehr für dieses Mandat durchgeführt
(Az-Treffer ist eindeutiger als jeder Namens-Treffer). Pro Mandat wird
höchstens EIN Kandidat erzeugt (die beste gefundene Stufe über Az,
`mandant` und `gegenseite`) — kein Mandat erscheint doppelt im Report.

Kein Kandidat für ein Mandat -> das Mandat erscheint nicht in
`kandidaten[]`. Eine leere `kandidaten`-Liste insgesamt bedeutet
`kein_treffer` — eine Lücke, die der Executor/Skill explizit als solche
ausweist (Anti-Halluzination: kein Mandat wird geraten).

Reine Funktionen, keine Persistierung, kein Netzwerkzugriff.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .az import az_gefunden_in_text
from .parteisuche import (
    STUFE_MOEGLICH,
    STUFE_TREFFER,
    SCHWELLE_MOEGLICH_DEFAULT,
    nachname,
    nachname_in_personen_position,
    suche_name_in_text,
)

# Suchfelder für den Parteiname-Abgleich (Z1-Z4), in dieser Priorität, falls
# derselbe Name in mehreren Feldern zugleich träfe (siehe `_bester_treffer`).
# `absender_adresse` (E-Mail-Adresse) ist bewusst AUSGESCHLOSSEN: eine
# E-Mail-Adresse ist kein Namens-Fließtext, ein Treffer dort wäre Zufall
# (z. B. generische Domain-Bestandteile) statt eines echten Namens-Fundes.
FELD_REIHENFOLGE: tuple[str, ...] = ("betreff", "textauszug", "absender_name")
# Aktenzeichen-Suche (Z0) ist enger gefasst als der Parteiname-Abgleich:
# nur Betreff/Textauszug (Auftragsvorgabe) — ein Aktenzeichen im
# Absendernamen wäre ohnehin untypisch.
AZ_SUCHFELDER: tuple[str, ...] = ("betreff", "textauszug")

# Stufe der Nachname-Korroboration: schwächer als jeder Vollnamen-`treffer`
# (Z1/Z2), aber stärker als die geratenen Schreibweisen-Stufen Z3/Z4 — daher
# die Zwischen-Ordnung 2.5 statt einer neuen Nummer am Ende der Leiter.
STUFE_NACHNAME = "Z2N"

_STUFE_ORDNUNG = {"Z0": 0, "Z1": 1, "Z2": 2, STUFE_NACHNAME: 2.5, "Z3": 3, "Z4": 4}


@dataclass
class Dokument:
    """Eingang für die Zuordnung — eine E-Mail (oder gleichwertige Metadaten)."""
    absender_name: str = ""
    absender_adresse: str = ""
    betreff: str = ""
    textauszug: str = ""


@dataclass
class Mandat:
    """Ein Eintrag der Mandatsliste (aus `core/context/schema.py:lese_mandate()`)."""
    az: str
    mandant: str = ""
    gegenseite: str | None = None
    datei: str | None = None  # Referenz für den Report (z. B. "mandate/2026-001.md")


@dataclass
class Kandidat:
    az: str
    stufe: str        # "Z0".."Z4"
    kategorie: str    # "treffer" | "moeglicher_treffer"
    score: float
    begruendung: str
    datei: str | None = None


def _bester_partei_treffer(name: str, dokument: Dokument,
                            schwelle: float) -> tuple[str, "object"] | None:
    """Sucht `name` über `FELD_REIHENFOLGE`, liefert (feldname, ParteiTreffer)
    der besten (niedrigsten Z-Stufe, bei Gleichstand höchstem Score)
    gefundenen Stelle, oder `None`, wenn keines der Felder trifft."""
    kandidaten: list[tuple[str, object]] = []
    for feldname in FELD_REIHENFOLGE:
        text = getattr(dokument, feldname, "")
        if not text:
            continue
        treffer = suche_name_in_text(name, text, schwelle)
        if treffer is not None:
            kandidaten.append((feldname, treffer))
    if not kandidaten:
        return None
    return min(kandidaten, key=lambda kv: (_STUFE_ORDNUNG[kv[1].stufe], -kv[1].score))


def vergleiche_dokument_mandat(dokument: Dokument, mandat: Mandat,
                                schwelle: float = SCHWELLE_MOEGLICH_DEFAULT) -> Kandidat | None:
    """Prüft ein (Dokument, Mandat)-Paar: erst Z0 (Az), dann Z1-Z4 (mandant,
    dann gegenseite). Gibt höchstens einen `Kandidaten` zurück."""
    # Z0 — Aktenzeichen wörtlich in Betreff/Textauszug.
    for feldname in AZ_SUCHFELDER:
        text = getattr(dokument, feldname, "")
        if text and az_gefunden_in_text(mandat.az, text):
            return Kandidat(
                az=mandat.az, stufe="Z0", kategorie=STUFE_TREFFER, score=1.0,
                begruendung=f"Aktenzeichen '{mandat.az}' wörtlich (nach Whitespace-"
                            f"Normalisierung) im Feld '{feldname}' gefunden",
                datei=mandat.datei)

    # Z1-Z4 — Parteiname (mandant, dann gegenseite).
    ergebnisse: list[tuple[str, str, object]] = []  # (rolle, feldname, ParteiTreffer)
    if mandat.mandant:
        treffer = _bester_partei_treffer(mandat.mandant, dokument, schwelle)
        if treffer is not None:
            ergebnisse.append(("mandant", treffer[0], treffer[1]))
    if mandat.gegenseite:
        treffer = _bester_partei_treffer(mandat.gegenseite, dokument, schwelle)
        if treffer is not None:
            ergebnisse.append(("gegenseite", treffer[0], treffer[1]))

    if not ergebnisse:
        return None

    rolle, feldname, treffer = min(
        ergebnisse, key=lambda e: (_STUFE_ORDNUNG[e[2].stufe], -e[2].score, e[0]))
    name = mandat.mandant if rolle == "mandant" else mandat.gegenseite
    begruendung = (f"Partei '{name}' (Rolle: {rolle}) per Stufe {treffer.stufe} im "
                   f"Feld '{feldname}' gefunden: {treffer.begruendung}")
    return Kandidat(az=mandat.az, stufe=treffer.stufe, kategorie=treffer.kategorie,
                     score=treffer.score, begruendung=begruendung, datei=mandat.datei)


def _nachnamen_signale(dokument: Dokument,
                        mandat: Mandat) -> dict[str, tuple[str, str]]:
    """`{nachname: (rolle, feldname)}` für jede Partei des Mandats, deren
    Nachname **wörtlich und in Personen-Position** im Dokument steht
    (`nachname_in_personen_position()`, dort begründet).

    Phonetische/fuzzy Fundstellen (Z3/Z4) zählen bewusst NICHT — Z2N ist
    schon die schwächere Namens-Evidenz, sie darf nicht zusätzlich auf
    geratenen Schreibweisen aufsetzen (Anti-Halluzination)."""
    nachnamen: dict[str, str] = {}  # nachname -> rolle (erste Rolle gewinnt)
    for rolle, name in (("mandant", mandat.mandant), ("gegenseite", mandat.gegenseite)):
        nn = nachname(name or "")
        if nn and nn not in nachnamen:
            nachnamen[nn] = rolle

    signale: dict[str, tuple[str, str]] = {}
    for nn, rolle in nachnamen.items():
        andere = set(nachnamen) - {nn}
        for feldname in FELD_REIHENFOLGE:
            text = getattr(dokument, feldname, "")
            if text and nachname_in_personen_position(nn, text, andere):
                signale[nn] = (rolle, feldname)
                break
    return signale


def _ergaenze_nachname_stufe(dokument: Dokument,
                              paare: list[tuple[Mandat, Kandidat | None]]) -> list[str]:
    """Setzt Stufe Z2N in `paare` (in-place), wo Vollname/Az nichts Besseres
    gefunden haben, und liefert die Enthaltungs-Hinweise zu mehrdeutigen
    Nachname-Signalen (siehe Modul-Docstring)."""
    signale = {}
    for i, (mandat, kandidat) in enumerate(paare):
        if kandidat is not None and _STUFE_ORDNUNG[kandidat.stufe] <= _STUFE_ORDNUNG[STUFE_NACHNAME]:
            continue  # bereits gleich gute oder bessere Stufe gefunden
        gefunden = _nachnamen_signale(dokument, mandat)
        if len(gefunden) >= 2:  # ein Nachname allein reicht nie
            signale[i] = gefunden

    haeufigkeit = Counter(nn for gefunden in signale.values() for nn in gefunden)
    hinweise: list[str] = []
    for i, gefunden in signale.items():
        mandat = paare[i][0]
        mehrdeutig = sorted(nn for nn in gefunden if haeufigkeit[nn] > 1)
        if mehrdeutig:
            hinweise.append(
                f"Mandat {mandat.az}: Nachname-Signal {{{', '.join(mehrdeutig)}}} trifft "
                f"auf mehrere Mandate zu — keine Zuordnung über Stufe "
                f"{STUFE_NACHNAME} (Enthaltung, Rückfrage an die Kanzlei).")
            continue
        belege = ", ".join(f"'{nn}' ({rolle}, Feld '{feld}')"
                           for nn, (rolle, feld) in sorted(gefunden.items()))
        paare[i] = (mandat, Kandidat(
            az=mandat.az, stufe=STUFE_NACHNAME, kategorie=STUFE_MOEGLICH, score=1.0,
            begruendung=(f"Nachnamen zweier Beteiligter desselben Mandats wörtlich und "
                         f"in Personen-Position (Anrede/Rubrum) im Dokument gefunden: "
                         f"{belege} — Vollname (Vorname/Titel) nicht belegt, deshalb "
                         f"nur '{STUFE_MOEGLICH}'"),
            datei=mandat.datei))
    return hinweise


def finde_kandidaten_mit_hinweisen(
        dokument: Dokument, mandate: list[Mandat],
        schwelle_moeglich: float = SCHWELLE_MOEGLICH_DEFAULT,
) -> tuple[list[Kandidat], list[str]]:
    """Wie `finde_kandidaten()`, liefert zusätzlich die Enthaltungs-Hinweise
    der Stufe Z2N — Fälle, in denen ein Nachname-Signal auf mehrere Mandate
    passt und deshalb bewusst KEIN Kandidat erzeugt wurde. Der Executor
    weist sie im Report aus, damit die Enthaltung sichtbar ist (statt als
    stilles `kein_treffer`)."""
    paare: list[tuple[Mandat, Kandidat | None]] = [
        (m, vergleiche_dokument_mandat(dokument, m, schwelle_moeglich)) for m in mandate
    ]
    hinweise = _ergaenze_nachname_stufe(dokument, paare)

    kandidaten = [k for _, k in paare if k is not None]
    kandidaten.sort(key=lambda k: (
        0 if k.kategorie == STUFE_TREFFER else 1,
        _STUFE_ORDNUNG.get(k.stufe, 9),
        -k.score,
        k.az,
    ))
    return kandidaten, hinweise


def finde_kandidaten(dokument: Dokument, mandate: list[Mandat],
                      schwelle_moeglich: float = SCHWELLE_MOEGLICH_DEFAULT) -> list[Kandidat]:
    """Vergleicht `dokument` gegen jedes Mandat in `mandate`, liefert die
    sortierte Kandidatenliste (treffer vor moeglicher_treffer, darin nach
    Stufe, dann absteigend nach Score, dann Az als Tie-Breaker).

    Eine leere Rückgabe ist `kein_treffer` — die aufrufende Stelle (Executor)
    weist das explizit als Lücke aus, statt ein Mandat zu raten."""
    return finde_kandidaten_mit_hinweisen(dokument, mandate, schwelle_moeglich)[0]
