"""
ATM_Website/server.py
Standard-library Python web server exposing the Project 10 ATM Simulator OOP backend
as a JSON API and serving the interactive ATM website.

Run with:
    python3 server.py
Then open http://127.0.0.1:8000 in your browser.
"""

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "static"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models import ATM, CurrentAccount, SavingsAccount  # noqa: E402


class ATMWebApp:
    """Thread-safe wrapper around the core ATM object for HTTP handlers."""

    def __init__(self, data_file: str | None = None, receipt_dir: str | None = None) -> None:
        self.lock = threading.Lock()
        self.atm = ATM(
            data_file=data_file or str(BASE_DIR / "data" / "atm_data.json"),
            receipt_dir=receipt_dir or str(BASE_DIR / "receipts"),
        )
        self.admin_logged_in = False

    def serialize_account(self, acc) -> dict:
        data = {
            "account_number": acc.account_number,
            "owner": acc.owner,
            "type": acc.account_type(),
            "balance": acc.balance,
            "is_blocked": acc.is_blocked,
            "failed_attempts": acc.failed_attempts,
            "per_tx_limit": acc.per_tx_limit,
            "daily_limit": acc.daily_limit,
            "daily_withdrawn": acc.daily_withdrawn,
            "min_balance": acc.min_balance,
            "mini_statement": acc.mini_statement(5),
        }
        if isinstance(acc, SavingsAccount):
            data["interest_rate"] = acc.interest_rate
            data["monthly_withdrawal_limit"] = acc.monthly_withdrawal_limit
            data["monthly_withdrawals"] = acc.monthly_withdrawals
        if isinstance(acc, CurrentAccount):
            data["overdraft_limit"] = acc.overdraft_limit
        return data

    def get_state(self) -> dict:
        with self.lock:
            current = (
                self.serialize_account(self.atm.current_account)
                if self.atm.current_account is not None
                else None
            )
            accounts_summary = [
                {
                    "account_number": acc.account_number,
                    "owner": acc.owner,
                    "type": acc.account_type(),
                    "is_blocked": acc.is_blocked,
                }
                for acc in self.atm.accounts.values()
            ]
            return {
                "logged_in": current is not None,
                "current_account": current,
                "admin_logged_in": self.admin_logged_in,
                "atm_total_cash": self.atm.dispenser.total_cash(),
                "notes": {str(k): v for k, v in sorted(self.atm.dispenser.notes.items(), reverse=True)},
                "accounts_list": accounts_summary,
                "startup_message": self.atm.startup_message,
            }

    def handle_action(self, path: str, body: dict) -> tuple[int, dict]:
        with self.lock:
            if path == "/api/login":
                ok, msg = self.atm.login(
                    str(body.get("account_number", "")),
                    str(body.get("pin", "")),
                )
                acc = self.serialize_account(self.atm.current_account) if ok else None
                return HTTPStatus.OK, {"ok": ok, "message": msg, "account": acc}

            if path == "/api/logout":
                msg = self.atm.logout()
                return HTTPStatus.OK, {"ok": True, "message": msg}

            if path == "/api/deposit":
                amount = _to_float(body.get("amount"))
                if amount is None:
                    return HTTPStatus.BAD_REQUEST, {"ok": False, "message": "Enter a valid numeric amount."}
                ok, msg, info = self.atm.deposit(amount)
                acc = self.serialize_account(self.atm.current_account) if self.atm.current_account else None
                return HTTPStatus.OK, {"ok": ok, "message": msg, "info": info, "account": acc}

            if path == "/api/withdraw":
                amount = _to_float(body.get("amount"))
                if amount is None:
                    return HTTPStatus.BAD_REQUEST, {"ok": False, "message": "Enter a valid numeric amount."}
                ok, msg, info = self.atm.withdraw(amount)
                acc = self.serialize_account(self.atm.current_account) if self.atm.current_account else None
                return HTTPStatus.OK, {
                    "ok": ok,
                    "message": msg,
                    "info": info,
                    "account": acc,
                    "atm_total_cash": self.atm.dispenser.total_cash(),
                }

            if path == "/api/transfer":
                amount = _to_float(body.get("amount"))
                if amount is None:
                    return HTTPStatus.BAD_REQUEST, {"ok": False, "message": "Enter a valid numeric amount."}
                ok, msg, info = self.atm.transfer(str(body.get("to_account_number", "")), amount)
                acc = self.serialize_account(self.atm.current_account) if self.atm.current_account else None
                return HTTPStatus.OK, {"ok": ok, "message": msg, "info": info, "account": acc}

            if path == "/api/change-pin":
                ok, msg = self.atm.change_pin(
                    str(body.get("old_pin", "")),
                    str(body.get("new_pin", "")),
                )
                return HTTPStatus.OK, {"ok": ok, "message": msg}

            if path == "/api/apply-interest":
                ok, msg, info = self.atm.apply_interest_current()
                acc = self.serialize_account(self.atm.current_account) if self.atm.current_account else None
                return HTTPStatus.OK, {"ok": ok, "message": msg, "info": info, "account": acc}

            if path == "/api/admin/login":
                pin = str(body.get("pin", ""))
                if self.atm.verify_admin_pin(pin):
                    self.admin_logged_in = True
                    return HTTPStatus.OK, {"ok": True, "message": "Admin login successful."}
                return HTTPStatus.OK, {"ok": False, "message": "Incorrect Admin PIN."}

            if path == "/api/admin/logout":
                self.admin_logged_in = False
                return HTTPStatus.OK, {"ok": True, "message": "Exited Admin Mode."}

            if path == "/api/admin/create-account":
                if not self.admin_logged_in:
                    return HTTPStatus.FORBIDDEN, {"ok": False, "message": "Admin authentication required."}
                bal = _to_float(body.get("initial_balance"))
                if bal is None:
                    return HTTPStatus.BAD_REQUEST, {"ok": False, "message": "Invalid initial balance."}
                ok, msg = self.atm.admin_create_account(
                    str(body.get("account_number", "")),
                    str(body.get("owner", "")),
                    str(body.get("pin", "")),
                    bal,
                    str(body.get("account_type", "Savings")),
                )
                return HTTPStatus.OK, {"ok": ok, "message": msg}

            if path == "/api/admin/unblock":
                if not self.admin_logged_in:
                    return HTTPStatus.FORBIDDEN, {"ok": False, "message": "Admin authentication required."}
                ok, msg = self.atm.admin_unblock_account(str(body.get("account_number", "")))
                return HTTPStatus.OK, {"ok": ok, "message": msg}

            if path == "/api/admin/restock":
                if not self.admin_logged_in:
                    return HTTPStatus.FORBIDDEN, {"ok": False, "message": "Admin authentication required."}
                denom = _to_int(body.get("denomination"))
                count = _to_int(body.get("count"))
                if denom is None or count is None:
                    return HTTPStatus.BAD_REQUEST, {"ok": False, "message": "Enter valid whole numbers."}
                ok, msg = self.atm.dispenser.restock(denom, count)
                if ok:
                    self.atm.save()
                return HTTPStatus.OK, {
                    "ok": ok,
                    "message": msg,
                    "atm_total_cash": self.atm.dispenser.total_cash(),
                }

            return HTTPStatus.NOT_FOUND, {"ok": False, "message": "Unknown API endpoint."}

    def get_admin_overview(self) -> tuple[int, dict]:
        with self.lock:
            if not self.admin_logged_in:
                return HTTPStatus.FORBIDDEN, {"ok": False, "message": "Admin authentication required."}
            return HTTPStatus.OK, {
                "ok": True,
                "accounts": [self.serialize_account(acc) for acc in self.atm.accounts.values()],
                "atm_total_cash": self.atm.dispenser.total_cash(),
                "notes": {str(k): v for k, v in sorted(self.atm.dispenser.notes.items(), reverse=True)},
                "statistics": self.atm.get_statistics(),
            }


def _to_float(val) -> float | None:
    try:
        return float(str(val).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _to_int(val) -> int | None:
    try:
        return int(str(val).strip())
    except (TypeError, ValueError):
        return None


def make_handler(app: ATMWebApp):
    """Create a request handler bound to a specific ATMWebApp instance."""

    class ATMRequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            # Keep terminal clean while still showing requests briefly
            pass

        def _send_json(self, status: int, payload: dict) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_file(self, file_path: Path, content_type: str) -> None:
            if not file_path.exists() or not file_path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                return
            data = file_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            parsed = urlparse(self.path).path
            if parsed == "/api/state":
                self._send_json(HTTPStatus.OK, app.get_state())
                return
            if parsed == "/api/admin/overview":
                status, payload = app.get_admin_overview()
                self._send_json(status, payload)
                return

            if parsed == "/" or parsed == "/index.html":
                self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            elif parsed == "/styles.css":
                self._send_file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
            elif parsed == "/app.js":
                self._send_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def do_POST(self) -> None:
            parsed = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                body = json.loads(raw_body.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "message": "Invalid JSON body."})
                return

            status, payload = app.handle_action(parsed, body)
            self._send_json(status, payload)

    return ATMRequestHandler


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    app = ATMWebApp()
    server = None
    chosen_port = port
    for candidate in range(port, port + 10):
        try:
            server = ThreadingHTTPServer((host, candidate), make_handler(app))
            chosen_port = candidate
            break
        except OSError:
            continue

    if server is None:
        raise RuntimeError(f"No available port found in range {port}-{port + 9}.")

    print(f"ATM Simulator Website running at http://{host}:{chosen_port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
