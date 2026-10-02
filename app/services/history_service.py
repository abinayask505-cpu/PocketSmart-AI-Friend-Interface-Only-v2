import json
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "history.json"
DATA_DIR.mkdir(exist_ok=True)


def _load():
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items):
    HISTORY_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def save_history(email, category, input_data, result):
    items = _load()
    items.append({
        "id": len(items) + 1,
        "email": email,
        "category": category,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": input_data,
        "result": result,
    })
    _save(items)


def get_history(email):
    return [x for x in _load() if x["email"] == email]
