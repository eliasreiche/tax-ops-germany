#!/usr/bin/env python3
"""rechenschritt — ein Glied der nachvollziehbaren Rechenkette (P3).

Jeder Rechner in `core/calc/` (Fristen, RVG, GKG) weist seine Zwischen-
ergebnisse als nummerierte Kette aus Norm + Beschreibung + Ergebnis aus.
Die Struktur ist überall dieselbe und steht deshalb hier einmal.

`quelle="executor"` ist der Deterministik-Nachweis: der Wert stammt aus dem
Executor, nie aus dem Modell (CONVENTIONS.md P3).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RechenSchritt:
    schritt: int
    norm: str
    beschreibung: str
    ergebnis: str | None
    quelle: str = "executor"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
