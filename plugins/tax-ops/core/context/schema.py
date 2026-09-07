"""core/context/schema — Kontrakt und reine Prüf-Logik des `kontext/`-Ordners (P3).

Öffentliche API, genutzt von `validator.py` (CLI) und von
`core/calc/retention/executor.py` (liest `mandatsende`/`status` für die
Retention-Berechnung, ohne das Schema ein zweites Mal zu parsen).

`kontext/` ist die EINZIGE Schnittstelle der Skills zu Kanzlei-Wissen (D11):

    kontext/
      kanzlei.md          Kanzlei-Profil (Pflicht)
      kontakte.md          Kontaktliste (empfohlen)
      mandate/<az>.md       ein File je Mandat (Schema siehe unten)
      posteingang/          optional, unstrukturierte Eingänge
      export/               optional, ausgehende Schreiben/Exporte

Vollständige Doku: `core/context/README.md`. Nur Standardbibliothek — kein
PyYAML, damit der Validator ohne Installation läuft (wie der Struktur-Lint).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # nur für die Typannotation von lese_kontext_mandate()
    from zuordnung import Mandat

# --------------------------------------------------------------------------
# Konstanten (Schema-Kontrakt)
# --------------------------------------------------------------------------

STATUS_WERTE = {"aktiv", "ruhend", "beendet"}
PFLICHTFELDER_MANDAT = ("az", "mandant", "stand")
# Felder, deren SCHLÜSSEL im Frontmatter vorhanden sein sollte (Wert darf
# null sein) — fehlt der Schlüssel ganz, ist das nur eine Warnung, weil z. B.
# core/calc/retention/executor.py sonst nicht weiß, ob ein Mandat überhaupt
# retentionsfähig ist.
EMPFOHLENE_SCHLUESSEL_MANDAT = ("gegenseite", "mandatsende", "streitwert", "status")
ABSCHNITTE_MANDAT = ("## Parteien", "## Kommunikation", "## Letzter Schritt",
                    "## Nächste Frist")
# Dokumentierte Bereiche des kontext/-Ordners — einzige Quelle; der
# Struktur-Lint (core/verify/struktur_lint.py) importiert sie von hier für
# die Prüfung von kontext_reads/kontext_writes.
KONTEXT_BEREICHE = ("kanzlei.md", "mandate/", "kontakte.md", "posteingang/", "export/")

ISO_DATUM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NULL_WERTE = ("", "null", "~", "None")


class KontextEingabeFehler(Exception):
    """`kontext/`-Datei nicht lesbar (z. B. Binärdatei statt Markdown/Text).

    Wird von den drei Lesestellen dieses Moduls geworfen, die Dateiinhalte
    öffnen (`pruefe_mandat_datei`, `pruefe_kanzlei_datei`, `lese_mandate`).
    Aufrufende CLIs fangen sie für den dokumentierten Eingabefehler-Exit (2).
    """

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_FELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$")
_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


# --------------------------------------------------------------------------
# Frontmatter (flach, key: value) — mit Zeilennummern für datei:zeile-Meldungen
# --------------------------------------------------------------------------

def lade_frontmatter(text: str) -> dict[str, tuple[str | None, int]] | None:
    """Liest den YAML-Frontmatter-Block als {feld: (wert, zeilennummer)}.

    `wert` ist `None` bei explizitem YAML-null (leerer Wert, `null`, `~`).
    Die Zeilennummer ist 1-basiert relativ zum Dateianfang (Zeile 1 = `---`).
    Gibt `None` zurück, wenn kein Frontmatter-Block gefunden wurde.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    felder: dict[str, tuple[str | None, int]] = {}
    for i, zeile in enumerate(m.group(1).splitlines(), start=2):  # Zeile 1 = '---'
        km = _FELD_RE.match(zeile)
        if not km:
            continue
        wert = km.group(2).strip()
        if len(wert) >= 2 and wert[0] == wert[-1] and wert[0] in "'\"":
            wert = wert[1:-1]
        felder[km.group(1)] = (None if wert in _NULL_WERTE else wert, i)
    return felder


# --------------------------------------------------------------------------
# Mandats-Datei (mandate/<az>.md)
# --------------------------------------------------------------------------

def pruefe_mandat_text(text: str, ref: str) -> tuple[list[str], list[str]]:
    """Prüft den Text einer Mandats-Datei gegen das Schema.

    `ref` ist der Anzeigename der Datei für Fehlermeldungen (z. B. relativer
    Pfad). Gibt (fehler, warnungen) zurück — beide als Liste von
    `ref:zeile: Meldung`-Strings (Zeile entfällt bei Meldungen ohne
    Zeilenbezug).
    """
    fehler: list[str] = []
    warnungen: list[str] = []

    fm = lade_frontmatter(text)
    if fm is None:
        fehler.append(f"{ref}:1: kein Frontmatter-Block")
        return fehler, warnungen

    for feld in PFLICHTFELDER_MANDAT:
        eintrag = fm.get(feld)
        if eintrag is None or not (eintrag[0] or "").strip():
            zeile = eintrag[1] if eintrag else 1
            fehler.append(f"{ref}:{zeile}: Pflichtfeld '{feld}' fehlt oder ist leer")

    stand = fm.get("stand")
    if stand is not None and stand[0] is not None and not ISO_DATUM_RE.match(stand[0]):
        fehler.append(f"{ref}:{stand[1]}: 'stand' ist kein ISO-Datum (JJJJ-MM-TT): "
                      f"{stand[0]!r}")

    for feld in EMPFOHLENE_SCHLUESSEL_MANDAT:
        if feld not in fm:
            warnungen.append(f"{ref}: empfohlenes Feld '{feld}' fehlt im Frontmatter "
                             f"(als 'null' setzen, falls (noch) nicht zutreffend)")

    mandatsende = fm.get("mandatsende")
    if mandatsende is not None and mandatsende[0] is not None:
        if not ISO_DATUM_RE.match(mandatsende[0]):
            fehler.append(f"{ref}:{mandatsende[1]}: 'mandatsende' ist weder ISO-Datum "
                          f"noch null: {mandatsende[0]!r}")

    streitwert = fm.get("streitwert")
    if streitwert is not None and streitwert[0] is not None:
        try:
            float(streitwert[0].replace(".", "").replace(",", "."))
        except ValueError:
            fehler.append(f"{ref}:{streitwert[1]}: 'streitwert' ist weder Zahl noch "
                          f"null: {streitwert[0]!r}")

    status = fm.get("status")
    if status is not None and status[0] is not None and status[0] not in STATUS_WERTE:
        fehler.append(f"{ref}:{status[1]}: 'status' muss einer von "
                      f"{sorted(STATUS_WERTE)} sein, ist: {status[0]!r}")

    for abschnitt in ABSCHNITTE_MANDAT:
        if abschnitt not in text:
            fehler.append(f"{ref}: Pflicht-Abschnitt '{abschnitt}' fehlt")

    if "## Nächste Frist" in text:
        rumpf = text.split("## Nächste Frist", 1)[1]
        rumpf = rumpf.split("\n## ", 1)[0]
        if "@" not in rumpf and "keine offene frist" not in rumpf.lower():
            warnungen.append(f"{ref}: Abschnitt 'Nächste Frist' enthält keinen "
                             f"erkennbaren iCal-UID-Verweis (Format "
                             f"'<hash>@fristenrechner.legal-ops') und auch keinen "
                             f"expliziten Hinweis auf 'keine offene Frist' — Verweis "
                             f"statt Neuberechnung erwartet (P3)")

    return fehler, warnungen


def pruefe_mandat_datei(pfad: Path, ref: str | None = None) -> tuple[list[str], list[str]]:
    """Wie `pruefe_mandat_text`, liest die Datei selbst; prüft zusätzlich
    Verweis-Integrität relativer Markdown-Links (Warnung, nicht Fehler)."""
    ref = ref or str(pfad)
    if not pfad.is_file():
        return [f"{ref}: Datei nicht gefunden"], []
    try:
        text = pfad.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise KontextEingabeFehler(f"{ref}: keine gültige UTF-8-Datei ({exc})") from exc
    fehler, warnungen = pruefe_mandat_text(text, ref)

    for m in _LINK_RE.finditer(text):
        ziel = m.group(1).strip()
        if ziel.startswith(("http://", "https://", "mailto:", "#")):
            continue
        pfad_teil = ziel.split("#", 1)[0].strip()
        if not pfad_teil:
            continue
        aufgeloest = (pfad.parent / pfad_teil)
        if not aufgeloest.is_file():
            zeile = text[:m.start()].count("\n") + 1
            warnungen.append(f"{ref}:{zeile}: Verweis-Ziel nicht gefunden: {pfad_teil}")

    return fehler, warnungen


# --------------------------------------------------------------------------
# kanzlei.md — bewusst leichtgewichtig geprüft (nur Existenz + H1)
# --------------------------------------------------------------------------

def pruefe_kanzlei_datei(pfad: Path) -> tuple[list[str], list[str]]:
    ref = str(pfad)
    if not pfad.is_file():
        return [f"{ref}: Pflichtdatei fehlt"], []
    try:
        text = pfad.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise KontextEingabeFehler(f"{ref}: keine gültige UTF-8-Datei ({exc})") from exc
    warnungen: list[str] = []
    if not re.search(r"^#\s+\S", text, re.MULTILINE):
        warnungen.append(f"{ref}: keine H1-Überschrift (Kanzleiname) gefunden")
    return [], warnungen


# --------------------------------------------------------------------------
# Ganzes kontext/-Verzeichnis
# --------------------------------------------------------------------------

def pruefe_kontext_verzeichnis(kontext: Path) -> tuple[list[str], list[str], int]:
    """Prüft ein komplettes `kontext/`-Verzeichnis. Gibt (fehler, warnungen,
    anzahl_mandate) zurück."""
    fehler: list[str] = []
    warnungen: list[str] = []

    kanzlei_fehler, kanzlei_warn = pruefe_kanzlei_datei(kontext / "kanzlei.md")
    fehler += kanzlei_fehler
    warnungen += kanzlei_warn

    if not (kontext / "kontakte.md").is_file():
        warnungen.append(f"{kontext / 'kontakte.md'}: Datei fehlt (empfohlen, nicht Pflicht)")

    mandate_dir = kontext / "mandate"
    anzahl = 0
    if not mandate_dir.is_dir():
        warnungen.append(f"{mandate_dir}: Ordner fehlt")
    else:
        for datei in sorted(mandate_dir.glob("*.md")):
            anzahl += 1
            m_fehler, m_warn = pruefe_mandat_datei(datei)
            fehler += m_fehler
            warnungen += m_warn

    return fehler, warnungen, anzahl


def lese_mandate(kontext: Path) -> list[tuple[Path, dict[str, tuple[str | None, int]]]]:
    """Liest alle `mandate/*.md`-Frontmatter eines `kontext/`-Verzeichnisses ein
    (für core/calc/retention/executor.py) — keine erneute Schema-Prüfung,
    nur das rohe Frontmatter je Datei. Dateien ohne lesbaren Frontmatter-Block
    werden ausgelassen (der Validator meldet sie separat als Fehler)."""
    mandate_dir = kontext / "mandate"
    ergebnis: list[tuple[Path, dict[str, tuple[str | None, int]]]] = []
    if not mandate_dir.is_dir():
        return ergebnis
    for datei in sorted(mandate_dir.glob("*.md")):
        try:
            text = datei.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise KontextEingabeFehler(
                f"{datei}: keine gültige UTF-8-Datei ({exc})") from exc
        fm = lade_frontmatter(text)
        if fm is not None:
            ergebnis.append((datei, fm))
    return ergebnis


def lese_kontext_mandate(kontext: Path) -> tuple[list[Mandat], list[str]]:
    """`kontext/mandate/*.md` als Zuordnungs-Mandatsliste (keine erneute
    Schema-Prüfung, dafür ist `validator.py` zuständig).

    Mandate ohne Aktenzeichen können nicht zugeordnet werden — sie werden
    übersprungen und als Warnung ausgewiesen, statt geraten zu werden.
    Genutzt von `email-akten-zuordnung`, `passive-zeiterfassung` und
    `posteingang-ocr-verteilung`.
    """
    # `Mandat` liegt in core/calc/zuordnung — erst hier importiert (Pfad-Muster
    # wie core/verify/provenienz.py). Modulglobal würde jeder Importeur dieses
    # Schema-Moduls (u. a. core/verify/struktur_lint.py) die halbe
    # Rechen-Bibliothek mitladen, obwohl er nur den Frontmatter-Parser braucht.
    _calc_dir = str(Path(__file__).resolve().parents[1] / "calc")
    if _calc_dir not in sys.path:
        sys.path.insert(0, _calc_dir)
    from zuordnung import Mandat

    warnungen: list[str] = []
    mandate: list[Mandat] = []
    for pfad, fm in lese_mandate(kontext):
        az = (fm.get("az") or (None, None))[0]
        if not az:
            warnungen.append(f"{pfad}: kein Aktenzeichen im Frontmatter — Mandat "
                             f"wird übersprungen (nicht zuordenbar)")
            continue
        mandant = (fm.get("mandant") or (None, None))[0] or ""
        gegenseite = (fm.get("gegenseite") or (None, None))[0]
        try:
            datei_rel = str(pfad.relative_to(kontext))
        except ValueError:
            datei_rel = str(pfad)
        mandate.append(Mandat(az=az, mandant=mandant, gegenseite=gegenseite,
                              datei=datei_rel))
    return mandate, warnungen
