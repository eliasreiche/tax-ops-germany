"""Regressionstest (Binärdatei-Guard-Nachzug, analog zum email-akten-
zuordnung-Fix): eine Binärdatei im `--kontext`-Verzeichnis darf keinen
Traceback erzeugen, sondern muss als sauberer Eingabefehler (Exit 2) enden.
`core/context/validator.py` --kontext geht über `pruefe_kontext_verzeichnis()`
in `schema.py`, die `UnicodeDecodeError` beim Lesen von `mandate/*.md` in
`KontextEingabeFehler` übersetzt.

Eindeutiger Testdateiname, damit er im selben pytest-Lauf nicht mit
gleichnamigen Tests anderer Skills kollidiert (mehrere Skills heißen
`executor.py`/`validator.py`).
"""
from __future__ import annotations

from conftest import CORE, lauf  # noqa: E402

VALIDATOR = CORE / "context" / "validator.py"

_PNG_BYTES = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x01])


def test_cli_binaeres_mandat_im_kontext_exit2_kein_traceback(tmp_path):
    kontext = tmp_path / "kontext"
    (kontext / "mandate").mkdir(parents=True)
    (kontext / "mandate" / "akte.md").write_bytes(_PNG_BYTES)
    (kontext / "kanzlei.md").write_text("# Kanzlei\n", encoding="utf-8")
    (kontext / "kontakte.md").write_text("# Kontakte\n", encoding="utf-8")

    ergebnis = lauf(VALIDATOR, "--kontext", kontext)

    assert ergebnis.returncode == 2, ergebnis.stderr
    assert ergebnis.stderr.startswith("Fehler:")
    assert "keine gültige UTF-8-Datei" in ergebnis.stderr
    assert "Traceback" not in ergebnis.stderr
