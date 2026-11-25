"""
storage.py — Member C (Data & Reports)
Handles PIN hashing, JSON persistence with error handling,
text receipt saving, and ATM transaction statistics.
"""

from datetime import datetime
import hashlib
import json
from pathlib import Path


def hash_pin(pin: str) -> str:
    """Return the SHA-256 hex digest of a PIN string."""
    return hashlib.sha256(pin.strip().encode("utf-8")).hexdigest()


def load_data(filepath: str) -> tuple[dict | None, str | None]:
    """
    Load ATM state from a JSON file.

    Returns:
        (data_dict, None) if loaded successfully.
        (None, status_message) if missing, empty, or corrupted.
    """
    path = Path(filepath)
    if not path.exists():
        return None, f"Data file '{filepath}' not found. Preloading default accounts."

    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        return None, f"Could not read '{filepath}' ({exc}). Preloading default accounts."

    if not raw:
        return None, f"Data file '{filepath}' is empty. Preloading default accounts."

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, f"Data file '{filepath}' is corrupted. Preloading default accounts."

    if not isinstance(data, dict) or "accounts" not in data:
        return None, f"Data file '{filepath}' has invalid format. Preloading default accounts."

    return data, None


def save_data(
    filepath: str,
    accounts: dict,
    notes: dict[int, int],
    admin_pin_hash: str,
) -> None:
    """Save all accounts, ATM note inventory, and admin PIN hash to JSON."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "admin_pin_hash": admin_pin_hash,
        "notes": {str(denom): count for denom, count in notes.items()},
        "accounts": {
            acc_num: acc.to_dict() for acc_num, acc in accounts.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_receipt(
    receipt_text: str,
    account_number: str,
    receipt_dir: str = "receipts",
) -> str:
    """Save a formatted transaction receipt to a text file and return its path."""
    folder = Path(receipt_dir)
    folder.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"receipt_{account_number}_{stamp}.txt"
    path = folder / filename
    path.write_text(receipt_text, encoding="utf-8")
    return str(path)


def compute_statistics(accounts: dict) -> dict:
    """
    Calculate summary statistics across all accounts:
    - counts per transaction type
    - largest deposit (amount, account_number, timestamp)
    - largest withdrawal (amount, account_number, timestamp)
    - busiest hour of the day (hour_int, count)
    """
    counts_by_type: dict[str, int] = {}
    hour_counts: dict[int, int] = {}
    largest_deposit = None
    largest_withdrawal = None

    for acc_num, account in accounts.items():
        for tx in account.transactions:
            tx_type = tx.get("type", "unknown")
            amount = float(tx.get("amount", 0.0))
            timestamp = tx.get("timestamp", "")

            counts_by_type[tx_type] = counts_by_type.get(tx_type, 0) + 1

            if tx_type == "deposit":
                if largest_deposit is None or amount > largest_deposit[0]:
                    largest_deposit = (amount, acc_num, timestamp)
            elif tx_type == "withdrawal":
                if largest_withdrawal is None or amount > largest_withdrawal[0]:
                    largest_withdrawal = (amount, acc_num, timestamp)

            if timestamp:
                try:
                    hour = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").hour
                    hour_counts[hour] = hour_counts.get(hour, 0) + 1
                except ValueError:
                    pass

    busiest_hour = None
    if hour_counts:
        top_hour = max(hour_counts, key=lambda h: hour_counts[h])
        busiest_hour = (top_hour, hour_counts[top_hour])

    return {
        "total_transactions": sum(counts_by_type.values()),
        "counts_by_type": counts_by_type,
        "largest_deposit": largest_deposit,
        "largest_withdrawal": largest_withdrawal,
        "busiest_hour": busiest_hour,
    }
