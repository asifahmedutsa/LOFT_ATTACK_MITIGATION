import os
from typing import Dict, List

import pandas as pd


def append_jsonl(path: str, row: Dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pd.DataFrame([row]).to_json(path, orient="records", lines=True, mode="a")


def write_table(path: str, rows: List[Dict]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)

