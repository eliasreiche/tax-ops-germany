"""Tests für core/verify/struktur_lint.py — der Lint ist selbst getestet.

1:1 aus `legal-ops-germany` übernommen und auf `tax-ops` angepasst
(`stberg_einordnung` statt `rdg_einordnung`, `bereich`-Werte, null Skills
als Startzustand) — siehe plugins/tax-ops/core/VENDORED.md.
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "plugins" / "tax-ops" / "core" / "verify"))

import struktur_lint  # noqa: E402


def _fehler(pruefung, *args) -> list[str]:
    """Ruft eine Lint-Prüfung mit frischer Fehlerliste auf und liefert
    sie zurück — die Liste ist bei allen Prüfungen das letzte Argument."""
    fehler: list[str] = []
    pruefung(*args, fehler)
    return fehler


def test_frontmatter_liest_quoted_werte():
    fm = struktur_lint.frontmatter(
        '---\nname: foo\nstatus: Work-in-progress\nhaftung: "Zweitkontrolle."\n---\n# x\n')
    assert fm == {"name": "foo", "status": "Work-in-progress",
                  "haftung": "Zweitkontrolle."}


def test_frontmatter_fehlt():
    assert struktur_lint.frontmatter("# kein Frontmatter\n") is None


def test_skill_dirs_findet_reale_skills():
    # Skills folgen ab Welle 6 (skills/README.md) — der Bootstrap-Startzustand
    # hatte bewusst null Skills (siehe core/VENDORED.md); seit stbvv-rechner
    # (Welle 6) ist mindestens einer vorhanden. Der Lint muss so oder so grün
    # laufen (siehe test_lint_laeuft_sauber_auf_dem_repo).
    assert len(struktur_lint.skill_dirs()) >= 1


def _skill(tmp_path, name, status, bereich="fristen", extra="", mit_tests=False):
    skill = tmp_path / name
    (skill / "tests").mkdir(parents=True)
    (skill / "tests" / ".gitkeep").write_text("")
    if mit_tests:
        (skill / "tests" / "test_x.py").write_text("def test_x(): pass\n")
    (skill / "SKILL.md").write_text(
        f'---\nname: {name}\ndescription: "x"\nstatus: {status}\nwelle: 6\n'
        f'bereich: {bereich}\n'
        f'stberg_einordnung: "x"\ndaten_hinweis: "x"\nhaftung: "x"\n{extra}---\n# x\n',
        encoding="utf-8")
    return skill


def test_pruefe_skill_meldet_fehlende_pflichtfelder(tmp_path):
    skill = tmp_path / "kaputter-skill"
    (skill / "tests").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: kaputter-skill\nstatus: stable\n---\n# x\n", encoding="utf-8")
    fehler = _fehler(struktur_lint.pruefe_skill, skill)
    meldungen = "\n".join(fehler)
    assert "description" in meldungen
    assert "stberg_einordnung" in meldungen
    assert "daten_hinweis" in meldungen
    assert "haftung" in meldungen
    assert "Work-in-progress`, `beta` oder `getestet" in meldungen


def test_pruefe_skill_meldet_unzulaessigen_bereich(tmp_path):
    fehler = _fehler(
        struktur_lint.pruefe_skill,
        _skill(tmp_path, "falscher-bereich-skill", "Work-in-progress",
               bereich="steuerrecht"))
    assert any("muss einer von" in f for f in fehler), fehler


def test_pruefe_skill_mit_gueltigem_bereich_ist_sauber(tmp_path):
    fehler = _fehler(
        struktur_lint.pruefe_skill,
        _skill(tmp_path, "gueltiger-skill", "Work-in-progress", bereich="compliance"))
    assert fehler == []


def test_beta_verlangt_echte_tests(tmp_path):
    fehler = _fehler(
        struktur_lint.pruefe_skill, _skill(tmp_path, "leerer-skill", "beta"))
    assert any("ohne Testdateien" in f for f in fehler)


def test_beta_mit_tests_ist_sauber(tmp_path):
    fehler = _fehler(struktur_lint.pruefe_skill,
                     _skill(tmp_path, "beta-skill", "beta", mit_tests=True))
    assert fehler == []


def test_getestet_verlangt_haendische_abnahme(tmp_path):
    fehler = _fehler(
        struktur_lint.pruefe_skill,
        _skill(tmp_path, "auto-skill", "getestet", mit_tests=True))
    assert any("haendisch_getestet" in f for f in fehler)


def test_getestet_mit_abnahme_und_tests_ist_sauber(tmp_path):
    fehler = _fehler(
        struktur_lint.pruefe_skill,
        _skill(tmp_path, "fertig-skill", "getestet",
               extra="haendisch_getestet: 2026-09-08\n", mit_tests=True))
    assert fehler == []


def test_lint_laeuft_sauber_auf_dem_repo():
    # Muss unabhängig von der Anzahl echter Skills grün durchlaufen — vor
    # Welle 6 mit 0, seit stbvv-rechner mit >= 1 (siehe
    # test_skill_dirs_findet_reale_skills).
    ergebnis = subprocess.run(
        [sys.executable, str(REPO / "plugins" / "tax-ops" / "core" / "verify" / "struktur_lint.py")],
        capture_output=True, text=True)
    assert ergebnis.returncode == 0, ergebnis.stderr
    assert "Struktur-Lint: sauber (" in ergebnis.stdout


# --------------------------------------------------------------------------
# Containment-Regel (Gate B) — Executor-Pfade und Doku-Links dürfen die
# Plugin-Grenze nicht verlassen. Genau die Regel, die den fehlenden-core-Bug
# gefangen hätte (siehe legal-ops-germany, D14).
# --------------------------------------------------------------------------

def _plugin_skill(tmp_path, name="demo-skill", skill_md="", core_files=()):
    """Baut plugins/tax-ops/{core,skills/<name>} unter tmp_path nach, damit
    plugin_root(skill) == .../tax-ops und ${CLAUDE_PLUGIN_ROOT} auf tax-ops
    zeigt."""
    plugin = tmp_path / "plugins" / "tax-ops"
    skill = plugin / "skills" / name
    skill.mkdir(parents=True)
    for rel in core_files:
        f = plugin / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x", encoding="utf-8")
    (skill / "SKILL.md").write_text(skill_md, encoding="utf-8")
    return skill


def test_containment_akzeptiert_plugin_relative_referenzen(tmp_path):
    md = ("# demo\n"
          "python3 ${CLAUDE_PLUGIN_ROOT}/core/calc/beispiel/executor.py --input x.json\n"
          "Siehe [Rechner](../../core/calc/beispiel/executor.py) und "
          "[Konvention](https://example.org/CONVENTIONS.md).\n")
    skill = _plugin_skill(tmp_path, skill_md=md,
                          core_files=["core/calc/beispiel/executor.py"])
    fehler = _fehler(struktur_lint.pruefe_containment, skill)
    assert fehler == [], fehler


def test_containment_meldet_escape_doku_link(tmp_path):
    md = "# demo\nSiehe [CONVENTIONS](../../../../CONVENTIONS.md).\n"
    skill = _plugin_skill(tmp_path, skill_md=md)
    fehler = _fehler(struktur_lint.pruefe_containment, skill)
    assert any("verlässt die Plugin-Grenze" in f for f in fehler), fehler


def test_containment_meldet_cwd_relativen_executor(tmp_path):
    md = "# demo\npython3 core/calc/beispiel/executor.py --input x.json\n"
    skill = _plugin_skill(tmp_path, skill_md=md,
                          core_files=["core/calc/beispiel/executor.py"])
    fehler = _fehler(struktur_lint.pruefe_containment, skill)
    assert any("nicht plugin-relativ" in f for f in fehler), fehler


def test_containment_meldet_fehlenden_executor(tmp_path):
    md = ("# demo\n"
          "python3 ${CLAUDE_PLUGIN_ROOT}/core/calc/fehlt/executor.py --input x.json\n")
    skill = _plugin_skill(tmp_path, skill_md=md)
    fehler = _fehler(struktur_lint.pruefe_containment, skill)
    assert any("existiert nicht" in f for f in fehler), fehler


# --------------------------------------------------------------------------
# Kontext-Layer — optionale kontext_reads/kontext_writes-Felder (unverändert
# aus legal-ops-germany übernommen).
# --------------------------------------------------------------------------

def test_liste_feld_block_stil():
    text = "---\nkontext_writes:\n  - mandate/*.md\n  - kontakte.md\n---\n# x\n"
    assert struktur_lint.liste_feld(text, "kontext_writes") == ["mandate/*.md", "kontakte.md"]


def test_liste_feld_flow_stil_ist_fehler():
    text = "---\nkontext_reads: [mandate/*.md, kontakte.md]\n---\n# x\n"
    with pytest.raises(ValueError, match="Block-Stil"):
        struktur_lint.liste_feld(text, "kontext_reads")


def test_pruefe_kontext_felder_muster_ohne_dokumentierten_bereich_ist_fehler():
    text = "---\nkontext_reads:\n  - irgendwo/x.md\n---\n"
    fehler = _fehler(struktur_lint.pruefe_kontext_felder, text, "ref")
    assert any("dokumentierten kontext/-Bereich" in f for f in fehler)


def test_pruefe_skill_ohne_kontext_felder_bleibt_gueltig(tmp_path):
    fehler = _fehler(struktur_lint.pruefe_skill,
                     _skill(tmp_path, "beta-skill", "beta", mit_tests=True))
    assert fehler == []


def test_pruefe_skill_mit_gueltigen_kontext_feldern_bleibt_gueltig(tmp_path):
    fehler = _fehler(
        struktur_lint.pruefe_skill,
        _skill(tmp_path, "beta-skill", "beta", mit_tests=True,
               extra="kontext_reads:\n  - mandate/*.md\nkontext_writes:\n  - kontakte.md\n"))
    assert fehler == []


def test_containment_meldet_mehrzeilige_cwd_relative_invocation(tmp_path):
    md = ("# demo\n"
          "python3 \\\n"
          "  core/calc/beispiel/executor.py \\\n"
          "  --input x.json\n")
    skill = _plugin_skill(tmp_path, skill_md=md,
                          core_files=["core/calc/beispiel/executor.py"])
    fehler = _fehler(struktur_lint.pruefe_containment, skill)
    assert any("nicht plugin-relativ" in f for f in fehler), fehler
