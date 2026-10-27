"""Lê o config.json e diz onde ficam os dados."""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"


def carregar(caminho: Path | None = None) -> dict:
    with open(caminho or RAIZ / "config.json", encoding="utf-8") as f:
        return json.load(f)
