"""core/calc/ao_fristen — AO-Fristberechnung (Einspruch, Abgabe, Vorauszahlung,
Verspätungszuschlag) nach der AO (P3).

Öffentliche API: siehe rechner.py; CLI: executor.py (JSON rein → JSON raus),
kalender_executor.py (Report rein → .ics/.csv raus).
"""
from .rechner import (  # noqa: F401
    AbgabefristErgebnis,
    AOEingabeFehler,
    AONichtAbgedeckt,
    EinspruchsfristErgebnis,
    RechenSchritt,
    VerspaetungszuschlagErgebnis,
    Verschiebung,
    VorauszahlungsErgebnis,
    berechne_abgabefrist,
    berechne_einspruchsfrist,
    berechne_verspaetungszuschlag,
    berechne_vorauszahlungstermine,
    fristart_nach_id,
    lade_abgabefristen,
    lade_fristarten,
    lade_vorauszahlungskatalog,
)
