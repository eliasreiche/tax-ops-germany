"""core/calc/triage — Posteingang-Priorisierung für Steuerkanzleien (P2/P3).

Öffentliche API: siehe rechner.py; CLI: executor.py (JSON rein → JSON raus).
"""
from .rechner import (  # noqa: F401
    Mandant,
    TriageEingabeFehler,
    ZuordnungTreffer,
    aufgabentitel_vorschlag,
    bewerte_mail,
    erkenne_indikatoren,
    extrahiere_bescheiddatum,
    extrahiere_steuernummern,
    finde_erledigt_vorschlaege,
    klassifiziere,
    lade_indikatoren,
    normalisiere_betreff,
    zuordne_mandant,
)
