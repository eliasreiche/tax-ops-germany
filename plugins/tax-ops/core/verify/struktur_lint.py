#!/usr/bin/env python3
"""Struktur-Lint — erzwingt die Hausregeln des Repos (siehe CONVENTIONS.md).

1:1 aus `legal-ops-germany` übernommen und auf `tax-ops` angepasst
(Pflichtfeld `rdg_einordnung` → `stberg_einordnung`, `bereich`-Werte,
Plugin-Pfad) — siehe core/VENDORED.md.

Prüft:
  * jedes SKILL.md trägt die Pflichtfelder name/description/status/welle/
    bereich/stberg_einordnung/daten_hinweis/haftung (Berufsrechts-Gate),
  * `bereich` ist einer der dokumentierten Prozessbereiche,
  * status ist `Work-in-progress`, `beta` oder `getestet` (Reifegrad-Leiter):
      - `Work-in-progress` = noch nicht entwickelt (Stub) oder Code ohne Test-Run
      - `beta`     = gegen Testdaten durch Agenten getestet (Orakel/Tests grün in CI)
                     → setzt echte Testdateien in tests/ voraus (.gitkeep zählt nicht)
      - `getestet` = live (händisch) getestet, keine Production-Garantie
                     → setzt außerdem `haendisch_getestet: <JJJJ-MM-TT>` im Frontmatter voraus,
  * name im Frontmatter == Verzeichnisname,
  * jedes Plugin hat .claude-plugin/plugin.json und README.md,
  * Containment (Auslieferungsgrenze): jeder von einer SKILL.md referenzierte
    Executor-Pfad und jeder relative Doku-Link löst INNERHALB des Plugin-
    Verzeichnisses auf — ein Pfad, der die Plugin-Grenze verlässt, ist ein
    Fehler (externe Verweise gehören als absolute URL, nicht als relativer Link),
  * die Status-Tabelle im Repo-README ist synchron (--check, Default in CI);
    --write-readme regeneriert sie.

Nur Standardbibliothek — kein PyYAML, damit der Lint ohne Installation läuft.
Exit-Code 0 = sauber, 1 = Verstöße (CI failt).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_CORE_DIR = Path(__file__).resolve().parents[1]  # core/
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from context.schema import KONTEXT_BEREICHE, lade_frontmatter  # noqa: E402

# struktur_lint.py liegt in plugins/tax-ops/core/verify/ — der Repo-Anker ist
# vier Ebenen höher (verify -> core -> tax-ops -> plugins -> REPO).
REPO = Path(__file__).resolve().parents[4]
LINT_PFAD = "plugins/tax-ops/core/verify/struktur_lint.py"
PFLICHTFELDER = ["name", "description", "status", "welle", "bereich",
                 "stberg_einordnung", "daten_hinweis", "haftung"]
STATUS_WERTE = {"Work-in-progress", "beta", "getestet"}
BEREICH_WERTE = {"fristen", "verguetung", "posteingang", "mandant",
                  "compliance", "wissen", "querschnitt"}
TABELLE_START = "<!-- skill-status:start -->"
TABELLE_ENDE = "<!-- skill-status:ende -->"

# Executor-Invocations in SKILL.md müssen plugin-relativ über diese Variable
# adressieren (Claude-Code-Plugin-Konvention: absolute Pfad zum installierten
# Plugin-Verzeichnis), damit sie ohne CWD-Annahme im Auslieferungs-Cache laufen.
PLUGIN_ROOT_VAR = "${CLAUDE_PLUGIN_ROOT}"
# Executor-Token einer Aufruf-Zeile (`python3 <token>`), inkl. der Variable.
_EXECUTOR_TOKEN_RE = re.compile(r"(\S*executor\.py)")
# Relative Markdown-Doku-Links [text](ziel).
_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# Kontext-Layer (D11, D19): optionale Frontmatter-Felder eines Skills, der
# kontext/ liest bzw. schreibt. Kein Pflichtfeld — bestehende Skills bleiben
# ohne diese Felder gültig. Werte sind Pfad-Muster relativ zu kontext/, siehe
# plugins/tax-ops/core/context/README.md. Die zulässigen Bereiche
# (KONTEXT_BEREICHE) kommen aus core/context/schema.py — eine Quelle.
KONTEXT_FELDER = ("kontext_reads", "kontext_writes")


def frontmatter(text: str) -> dict[str, str] | None:
    """Liest den YAML-Frontmatter-Block als flache key:value-Paare —
    dünne Sicht auf `context.schema.lade_frontmatter` (das zusätzlich
    Zeilennummern führt und YAML-null als `None` liefert)."""
    felder = lade_frontmatter(text)
    if felder is None:
        return None
    return {name: (wert or "") for name, (wert, _zeile) in felder.items()}


def liste_feld(text: str, feld: str) -> list[str] | None:
    """Liest ein optionales YAML-Listenfeld im Frontmatter-Block im Block-Stil
    (`feld:\\n  - a\\n  - b`). Gibt `None` zurück, wenn das Feld nicht vorkommt —
    unabhängig von `frontmatter()`, weil die dort verwendete flache
    key:value-Struktur keine Listen abbildet.

    Flow-Stil (`feld: [a, b]`) und einzelne Skalare (`feld: a`) sind bewusst
    NICHT zulässig und lösen einen `ValueError` aus (der Aufrufer meldet ihn
    als Lint-Verstoß) — eine Schreibweise je Feld, sonst driften die SKILL.md
    auseinander."""
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    zeilen = m.group(1).splitlines()
    for i, zeile in enumerate(zeilen):
        km = re.match(rf"^{re.escape(feld)}:\s*(.*)$", zeile)
        if not km:
            continue
        rest = km.group(1).strip()
        if rest:
            raise ValueError(
                f"`{feld}` muss im YAML-Block-Stil stehen (`{feld}:` gefolgt von "
                f"Zeilen `  - <muster>`) — gefunden: `{feld}: {rest}`")
        werte: list[str] = []
        for folge in zeilen[i + 1:]:
            fm2 = re.match(r"^\s*-\s*(.+)$", folge)
            if not fm2:
                break
            werte.append(fm2.group(1).strip().strip("'\""))
        return werte
    return None


def pruefe_kontext_felder(text: str, ref: object, fehler: list[str]) -> None:
    """Kontext-Layer (D11, D19): optionale `kontext_reads`/`kontext_writes` —
    wenn vorhanden, müssen Werte nicht-leere Strings sein und mit einem
    dokumentierten kontext/-Bereich beginnen (kein Pflichtfeld, siehe
    core/context/README.md)."""
    for feld in KONTEXT_FELDER:
        try:
            werte = liste_feld(text, feld)
        except ValueError as exc:
            fehler.append(f"{ref}: {exc}")
            continue
        if werte is None:
            continue
        if not werte:
            fehler.append(f"{ref}: `{feld}` ist als Liste vorhanden, aber leer")
            continue
        for muster in werte:
            if not muster.strip():
                fehler.append(f"{ref}: `{feld}` enthält ein leeres Muster")
            elif not muster.startswith(KONTEXT_BEREICHE):
                fehler.append(f"{ref}: `{feld}`-Muster `{muster}` beginnt nicht mit einem "
                              f"dokumentierten kontext/-Bereich "
                              f"({', '.join(KONTEXT_BEREICHE)})")


def skill_dirs() -> list[Path]:
    # Ein Plugin `tax-ops`; alle Skills liegen unter
    # plugins/tax-ops/skills/*. core/ enthält nur noch geteilte Rechner/Verifier
    # ohne eigenes SKILL.md. Skills folgen mit Welle 6 — leere Liste ist der
    # erwartete Startzustand und muss grün durchlaufen.
    return [p.parent for p in sorted(REPO.glob("plugins/*/skills/*/SKILL.md"))]


def plugin_root(skill: Path) -> Path:
    """Plugin-Wurzel eines Skills: plugins/<plugin>/skills/<name> -> parents[1]."""
    return skill.parents[1]


def _innerhalb(pfad: Path, wurzel: Path) -> bool:
    try:
        pfad.resolve().relative_to(wurzel.resolve())
        return True
    except ValueError:
        return False


def _ist_externer_link(ziel: str) -> bool:
    return ziel.startswith(("http://", "https://", "mailto:", "//")) or ziel.startswith("#")


def pruefe_containment(skill: Path, fehler: list[str]) -> None:
    """Containment-Regel (Auslieferungsgrenze): jeder Executor-Pfad und jeder
    relative Doku-Link einer SKILL.md muss innerhalb des Plugin-Verzeichnisses
    auflösen. Das ist genau die Regel, die den fehlenden `core/`-Bug gefangen
    hätte: ein Aufruf, der aus dem `source`-Dir hinauszeigt, ist im Install-Cache
    nicht lauffähig."""
    skill_md = skill / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return
    wurzel = plugin_root(skill)
    try:
        ref = skill.relative_to(REPO) / "SKILL.md"
    except ValueError:
        ref = skill / "SKILL.md"

    # (1) Executor-Invocations: nur Zeilen mit `python3 ... executor.py`.
    # Bash-Zeilenfortsetzungen (`\` am Zeilenende) vorher zu einer logischen
    # Zeile zusammenfassen, damit eine mehrzeilige Invocation (python3 \
    # <newline> ...executor.py) nicht an der Prüfung vorbeirutscht.
    for zeile in re.sub(r"\\\n[ \t]*", " ", text).splitlines():
        if "executor.py" not in zeile or "python" not in zeile:
            continue
        m = _EXECUTOR_TOKEN_RE.search(zeile)
        if not m:
            continue
        token = m.group(1).strip('"').strip("'")
        if token.startswith(PLUGIN_ROOT_VAR):
            rel = token[len(PLUGIN_ROOT_VAR):].lstrip("/")
            ziel = wurzel / rel
            if not _innerhalb(ziel, wurzel):
                fehler.append(f"{ref}: Executor-Pfad verlässt die Plugin-Grenze: {token}")
            elif not ziel.is_file():
                fehler.append(f"{ref}: referenzierter Executor existiert nicht: "
                              f"{token} (→ {ziel.relative_to(REPO) if _innerhalb(ziel, REPO) else ziel})")
        else:
            fehler.append(f"{ref}: Executor-Invocation ist nicht plugin-relativ — "
                          f"`{PLUGIN_ROOT_VAR}/...` erwartet (setzt sonst ein CWD "
                          f"voraus, im Install-Cache nicht lauffähig): {token}")

    # (2) Relative Doku-Links: müssen im Plugin bleiben.
    for m in _LINK_RE.finditer(text):
        ziel = m.group(1).strip()
        if _ist_externer_link(ziel):
            continue
        pfad_teil = ziel.split("#", 1)[0].strip()
        if not pfad_teil:  # reiner Anker
            continue
        if pfad_teil.startswith(PLUGIN_ROOT_VAR):
            aufgeloest = wurzel / pfad_teil[len(PLUGIN_ROOT_VAR):].lstrip("/")
        else:
            aufgeloest = skill_md.parent / pfad_teil
        if not _innerhalb(aufgeloest, wurzel):
            fehler.append(f"{ref}: Doku-Link verlässt die Plugin-Grenze: {ziel} "
                          f"— externe Verweise als absolute URL angeben, nicht als "
                          f"relativen Link")


def hat_echte_tests(skill: Path) -> bool:
    tests = skill / "tests"
    return tests.is_dir() and any(
        f.is_file() and f.name != ".gitkeep" for f in tests.rglob("*"))


def pruefe_skill(skill: Path, fehler: list[str]) -> dict[str, str] | None:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    fm = frontmatter(text)
    try:
        ref = skill.relative_to(REPO) / "SKILL.md"
    except ValueError:  # Skill außerhalb des Repos (z. B. in Tests)
        ref = skill / "SKILL.md"
    if fm is None:
        fehler.append(f"{ref}: kein Frontmatter-Block")
        return None
    pruefe_kontext_felder(text, ref, fehler)
    for feld in PFLICHTFELDER:
        if fm.get(feld, "").strip():
            continue
        fehler.append(f"{ref}: Pflichtfeld `{feld}` fehlt oder ist leer (Berufsrechts-Gate)")
    bereich = fm.get("bereich", "").strip()
    if bereich and bereich not in BEREICH_WERTE:
        fehler.append(f"{ref}: `bereich` muss einer von "
                      f"{', '.join(sorted(BEREICH_WERTE))} sein, ist: `{bereich}`")
    status = fm.get("status")
    if status not in STATUS_WERTE:
        fehler.append(f"{ref}: status muss `Work-in-progress`, `beta` oder `getestet` "
                      f"sein, ist: `{status}` (Reifegrad-Leiter)")
    if fm.get("name") != skill.name:
        fehler.append(f"{ref}: name `{fm.get('name')}` != Verzeichnis `{skill.name}`")
    if status in ("beta", "getestet") and not hat_echte_tests(skill):
        fehler.append(f"{ref}: status `{status}` ohne Testdateien in tests/ (Test-Disziplin)")
    if status == "getestet" and not re.match(
            r"^\d{4}-\d{2}-\d{2}$", fm.get("haendisch_getestet", "")):
        fehler.append(f"{ref}: status `getestet` verlangt "
                      f"`haendisch_getestet: <JJJJ-MM-TT>` im Frontmatter "
                      f"(händische Abnahme, D8-Nachtrag)")
    return fm


def pruefe_plugins(fehler: list[str]) -> None:
    plugins_dir = REPO / "plugins"
    if not plugins_dir.is_dir():
        # Isolierter Plugin-Cache (Install-Smoke-Test): kein Repo-Root mit
        # `plugins/`-Geschwistern vorhanden — dieser Meta-Check ergibt dort
        # keinen Sinn, das Skill-/Containment-Gate greift trotzdem.
        return
    for plugin in sorted(plugins_dir.iterdir()):
        # __pycache__ (aus plugins/conftest.py) und Punkt-Ordner sind keine
        # Plugins — sonst meldet der Lint sie als Plugin ohne plugin.json.
        if not plugin.is_dir() or plugin.name.startswith((".", "__")):
            continue
        if not (plugin / ".claude-plugin" / "plugin.json").is_file():
            fehler.append(f"plugins/{plugin.name}: .claude-plugin/plugin.json fehlt")
        if not (plugin / "README.md").is_file():
            fehler.append(f"plugins/{plugin.name}: README.md fehlt")


def status_tabelle(skills: list[tuple[Path, dict[str, str]]]) -> str:
    zeilen = ["| Skill | Bereich | Welle | Status |", "|---|---|---|---|"]
    def sortkey(eintrag):
        pfad, fm = eintrag
        return (int(fm.get("welle", "9")), fm.get("bereich", ""), fm.get("name", ""))
    for pfad, fm in sorted(skills, key=sortkey):
        rel = pfad.relative_to(REPO) / "SKILL.md"
        status = fm.get("status", "?")
        badge = {"getestet": "✅ `getestet`",
                 "beta": "🧪 `beta`"}.get(status, "🚧 `Work-in-progress`")
        zeilen.append(f"| [`{fm.get('name')}`]({rel}) | `{fm.get('bereich')}` "
                      f"| {fm.get('welle')} | {badge} |")
    return "\n".join(zeilen)


def readme_sync(tabelle: str, schreiben: bool, fehler: list[str]) -> None:
    readme = REPO / "README.md"
    if not readme.is_file():
        # Isolierter Plugin-Cache (Install-Smoke-Test): kein Repo-README
        # vorhanden — nichts zu synchronisieren.
        return
    text = readme.read_text(encoding="utf-8")
    if TABELLE_START not in text or TABELLE_ENDE not in text:
        fehler.append(f"README.md: Marker {TABELLE_START} / {TABELLE_ENDE} fehlen")
        return
    neu = re.sub(
        re.escape(TABELLE_START) + r".*?" + re.escape(TABELLE_ENDE),
        TABELLE_START + "\n" + tabelle + "\n" + TABELLE_ENDE,
        text, flags=re.DOTALL)
    if schreiben:
        if neu != text:
            readme.write_text(neu, encoding="utf-8")
            print("README.md: Status-Tabelle aktualisiert")
    elif neu != text:
        fehler.append("README.md: Status-Tabelle nicht synchron — "
                      f"`python3 {LINT_PFAD} --write-readme` ausführen")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-readme", action="store_true",
                        help="Status-Tabelle im README regenerieren statt nur prüfen")
    args = parser.parse_args()

    fehler: list[str] = []
    skills: list[tuple[Path, dict[str, str]]] = []
    for skill in skill_dirs():
        fm = pruefe_skill(skill, fehler)
        pruefe_containment(skill, fehler)
        if fm:
            skills.append((skill, fm))
    pruefe_plugins(fehler)
    readme_sync(status_tabelle(skills), args.write_readme, fehler)

    if fehler:
        print(f"Struktur-Lint: {len(fehler)} Verstöße\n", file=sys.stderr)
        for f in fehler:
            print(f"  ✗ {f}", file=sys.stderr)
        return 1
    print(f"Struktur-Lint: sauber ({len(skills)} Skills geprüft)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
