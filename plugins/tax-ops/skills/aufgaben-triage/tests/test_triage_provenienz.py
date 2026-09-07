"""Provenienz-Gate (P3): Bescheiddatum und Steuernummer-Muster
(`\\d{2,3}/\\d{3}/\\d{4,5}`) werden über `core/verify/provenienz.py` gegen
den Quelltext der Mail geprüft, bevor sie in den Report übernommen werden.
Da beide Werte per Regex direkt aus demselben Text extrahiert werden, ist
`nicht_belegt` im Normalbetrieb unerreichbar — dieser Test prüft die
Verdrahtung selbst: ein Wert, der NICHT im Quelltext steht, wird als
`nicht_belegt` erkannt und aus dem Report entfernt (Anti-Halluzination).
"""
from __future__ import annotations

from triage import executor as ex
from triage.rechner import extrahiere_steuernummern
from verify.provenienz import STATUS_BELEGT, STATUS_NICHT_BELEGT, pruefe_provenienz


def test_steuernummer_regex_extrahiert_erwartetes_muster():
    assert extrahiere_steuernummern("Ihre Steuernummer lautet 12/345/67890.") == \
        ["12/345/67890"]
    assert extrahiere_steuernummern("Kein Muster hier.") == []


def test_datum_wert_belegt_wenn_woertlich_im_text():
    werte = [{"pfad": "mail:1.bescheiddatum", "typ": "datum", "wert": "2026-02-03"}]
    quellen = [("mail:1:text", ["Bescheid vom 03.02.2026."])]
    ergebnisse = pruefe_provenienz(werte, quellen, ex.TYPEN)
    assert ergebnisse[0]["status"] == STATUS_BELEGT


def test_datum_wert_nicht_belegt_wenn_nicht_im_text():
    # Konstruierter Mismatch: der geprüfte Wert steht NICHT im Quelltext.
    werte = [{"pfad": "mail:1.bescheiddatum", "typ": "datum", "wert": "1999-01-01"}]
    quellen = [("mail:1:text", ["Bescheid vom 03.02.2026."])]
    ergebnisse = pruefe_provenienz(werte, quellen, ex.TYPEN)
    assert ergebnisse[0]["status"] == STATUS_NICHT_BELEGT
    assert ergebnisse[0]["fundstelle"] is None


def test_steuernummer_wert_nicht_belegt_wenn_nicht_im_text():
    werte = [{"pfad": "mail:1.steuernummer[0]", "typ": "steuernummer",
             "wert": "99/999/99999"}]
    quellen = [("mail:1:betreff", ["Betreff ohne Nummer"]),
              ("mail:1:text", ["Ihre Steuernummer lautet 12/345/67890."])]
    ergebnisse = pruefe_provenienz(werte, quellen, ex.TYPEN)
    assert ergebnisse[0]["status"] == STATUS_NICHT_BELEGT


def test_executor_provenienz_geprueft_verwirft_nicht_belegten_wert():
    # _provenienz_geprueft bekommt ein Bescheiddatum, das NICHT im
    # übergebenen Text steht (simulierter Extraktions-Bug) -> wird verworfen.
    bescheiddatum, steuernummern = ex._provenienz_geprueft(
        "mail-x", "Betreff", "Bescheid vom 03.02.2026.", "1999-01-01", ["12/345/67890"])
    assert bescheiddatum is None       # nicht belegt -> verworfen
    assert steuernummern == []         # ebenfalls nicht im Text -> verworfen


def test_executor_provenienz_geprueft_behaelt_belegte_werte():
    bescheiddatum, steuernummern = ex._provenienz_geprueft(
        "mail-x", "Betreff", "Bescheid vom 03.02.2026, Steuernummer 12/345/67890.",
        "2026-02-03", ["12/345/67890"])
    assert bescheiddatum == "2026-02-03"
    assert steuernummern == ["12/345/67890"]
