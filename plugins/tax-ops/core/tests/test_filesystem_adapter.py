"""Tests für core/adapters/filesystem/adapter.py — Referenz-Adapter (P2/P3).

Deckt ab: pull-Basisfall (Erstkopie), Idempotenz (unveränderte Quelle -> kein
Rewrite), sichere Aktualisierung (nur Quelle geändert), Konflikterkennung
(beide Seiten geändert -> .conflict-Datei + Exit 3, Zieldatei bleibt
unangetastet), push (Gegenrichtung), sowie die Eingabefehler-Fälle (Exit 2).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from conftest import ADAPTERS, lauf  # noqa: E402

ADAPTER = ADAPTERS / "filesystem" / "adapter.py"


def _lauf(*args: str) -> subprocess.CompletedProcess:
    return lauf(ADAPTER, *args)


def _setup(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    quelle = tmp_path / "quelle"
    kontext = tmp_path / "kontext"
    quelle.mkdir()
    manifest = tmp_path / "manifest.json"
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps(
        {"eintraege": [{"quelle": "akte.md", "kontext": "mandate/akte.md"}]}),
        encoding="utf-8")
    return quelle, kontext, manifest, mapping


def _pull(quelle, kontext, manifest, mapping) -> subprocess.CompletedProcess:
    return _lauf("pull", "--quelle", str(quelle), "--kontext", str(kontext),
                "--manifest", str(manifest), "--mapping", str(mapping))


def test_erster_pull_kopiert_und_legt_kontext_an(tmp_path):
    quelle, kontext, manifest, mapping = _setup(tmp_path)
    (quelle / "akte.md").write_text("Version 1", encoding="utf-8")

    res = _pull(quelle, kontext, manifest, mapping)
    assert res.returncode == 0, res.stderr
    assert (kontext / "mandate" / "akte.md").read_text(encoding="utf-8") == "Version 1"

    report = json.loads(res.stdout)
    assert report["ergebnisse"][0]["status"] == "synchronisiert"
    assert report["anzahl_konflikte"] == 0
    assert report["meta"]["quelle"] == "executor"
    assert manifest.is_file()


def test_zweiter_pull_ohne_aenderung_ist_idempotent(tmp_path):
    quelle, kontext, manifest, mapping = _setup(tmp_path)
    (quelle / "akte.md").write_text("Version 1", encoding="utf-8")
    _pull(quelle, kontext, manifest, mapping)

    ziel = kontext / "mandate" / "akte.md"
    mtime_vorher = ziel.stat().st_mtime_ns

    res = _pull(quelle, kontext, manifest, mapping)
    assert res.returncode == 0
    report = json.loads(res.stdout)
    assert report["ergebnisse"][0]["status"] == "unveraendert"
    assert ziel.stat().st_mtime_ns == mtime_vorher  # kein Rewrite


def test_pull_aktualisiert_wenn_nur_quelle_sich_aendert(tmp_path):
    quelle, kontext, manifest, mapping = _setup(tmp_path)
    (quelle / "akte.md").write_text("Version 1", encoding="utf-8")
    _pull(quelle, kontext, manifest, mapping)

    (quelle / "akte.md").write_text("Version 2", encoding="utf-8")
    res = _pull(quelle, kontext, manifest, mapping)
    assert res.returncode == 0
    report = json.loads(res.stdout)
    assert report["ergebnisse"][0]["status"] == "synchronisiert"
    assert (kontext / "mandate" / "akte.md").read_text(encoding="utf-8") == "Version 2"


def test_konflikt_wenn_beide_seiten_sich_aendern(tmp_path):
    quelle, kontext, manifest, mapping = _setup(tmp_path)
    (quelle / "akte.md").write_text("Version 1", encoding="utf-8")
    _pull(quelle, kontext, manifest, mapping)

    # Beide Seiten seit letztem Sync ändern.
    (quelle / "akte.md").write_text("Version 2 (Quelle)", encoding="utf-8")
    ziel = kontext / "mandate" / "akte.md"
    ziel.write_text("Lokal bearbeitet (Kontext)", encoding="utf-8")

    res = _pull(quelle, kontext, manifest, mapping)
    assert res.returncode == 3, res.stderr
    report = json.loads(res.stdout)
    assert report["anzahl_konflikte"] == 1
    assert report["ergebnisse"][0]["status"] == "konflikt"

    # Zieldatei NIEMALS stillschweigend überschrieben.
    assert ziel.read_text(encoding="utf-8") == "Lokal bearbeitet (Kontext)"
    konflikt_datei = ziel.with_name(ziel.name + ".conflict")
    assert konflikt_datei.is_file()
    assert konflikt_datei.read_text(encoding="utf-8") == "Version 2 (Quelle)"


def test_konflikt_ohne_baseline_wenn_ziel_bereits_abweicht(tmp_path):
    """Erster Sync überhaupt, aber die Zieldatei existiert schon mit anderem
    Inhalt -> konservativ als Konflikt behandeln (keine Baseline, um zu
    entscheiden, wer 'Recht' hat)."""
    quelle, kontext, manifest, mapping = _setup(tmp_path)
    (quelle / "akte.md").write_text("Quelle", encoding="utf-8")
    ziel_dir = kontext / "mandate"
    ziel_dir.mkdir(parents=True)
    (ziel_dir / "akte.md").write_text("Bereits vorhandener anderer Inhalt", encoding="utf-8")

    res = _pull(quelle, kontext, manifest, mapping)
    assert res.returncode == 3
    report = json.loads(res.stdout)
    assert report["anzahl_konflikte"] == 1


def test_erster_sync_mit_identischem_vorhandenem_ziel_ist_kein_konflikt(tmp_path):
    quelle, kontext, manifest, mapping = _setup(tmp_path)
    (quelle / "akte.md").write_text("Gleicher Inhalt", encoding="utf-8")
    ziel_dir = kontext / "mandate"
    ziel_dir.mkdir(parents=True)
    (ziel_dir / "akte.md").write_text("Gleicher Inhalt", encoding="utf-8")

    res = _pull(quelle, kontext, manifest, mapping)
    assert res.returncode == 0
    report = json.loads(res.stdout)
    assert report["anzahl_konflikte"] == 0


def test_push_synchronisiert_kontext_nach_quelle(tmp_path):
    quelle, kontext, manifest, mapping = _setup(tmp_path)
    (kontext / "mandate").mkdir(parents=True)
    (kontext / "mandate" / "akte.md").write_text("Aus kontext/", encoding="utf-8")

    res = _lauf("push", "--quelle", str(quelle), "--kontext", str(kontext),
               "--manifest", str(manifest), "--mapping", str(mapping))
    assert res.returncode == 0, res.stderr
    assert (quelle / "akte.md").read_text(encoding="utf-8") == "Aus kontext/"


def test_quelldatei_fehlt_ist_kein_harter_fehler(tmp_path):
    quelle, kontext, manifest, mapping = _setup(tmp_path)
    # akte.md existiert nirgends.
    res = _pull(quelle, kontext, manifest, mapping)
    assert res.returncode == 0
    report = json.loads(res.stdout)
    assert report["ergebnisse"][0]["status"] == "quelldatei_fehlt"


def test_pull_ohne_vorhandenes_quelle_verzeichnis_ist_exit_2(tmp_path):
    quelle, kontext, manifest, mapping = _setup(tmp_path)
    quelle.rmdir()
    res = _pull(quelle, kontext, manifest, mapping)
    assert res.returncode == 2
    assert "--quelle" in res.stderr


def test_push_ohne_vorhandenes_kontext_verzeichnis_ist_exit_2(tmp_path):
    quelle, kontext, manifest, mapping = _setup(tmp_path)
    res = _lauf("push", "--quelle", str(quelle), "--kontext", str(kontext),
               "--manifest", str(manifest), "--mapping", str(mapping))
    assert res.returncode == 2
    assert "--kontext" in res.stderr


def test_kaputtes_mapping_ist_exit_2(tmp_path):
    quelle, kontext, manifest, mapping = _setup(tmp_path)
    mapping.write_text("kein json{", encoding="utf-8")
    res = _pull(quelle, kontext, manifest, mapping)
    assert res.returncode == 2


def test_mapping_ohne_eintraege_ist_exit_2(tmp_path):
    quelle, kontext, manifest, mapping = _setup(tmp_path)
    mapping.write_text(json.dumps({"eintraege": []}), encoding="utf-8")
    res = _pull(quelle, kontext, manifest, mapping)
    assert res.returncode == 2
