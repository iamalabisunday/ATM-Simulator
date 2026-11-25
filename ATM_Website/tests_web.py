"""
ATM_Website/tests_web.py
Self-tests for the ATMWebApp API wrapper.
Run with: python3 ATM_Website/tests_web.py
"""

from pathlib import Path
import tempfile

from server import ATMWebApp


def test_web_app_flow() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        app = ATMWebApp(
            data_file=str(Path(tmp) / "atm_data.json"),
            receipt_dir=str(Path(tmp) / "receipts"),
        )

        state = app.get_state()
        assert state["logged_in"] is False
        assert state["atm_total_cash"] == 90000

        # Login Ada Obi (1001 / 4321)
        status, res = app.handle_action("/api/login", {"account_number": "1001", "pin": "4321"})
        assert status == 200 and res["ok"] is True
        assert res["account"]["owner"] == "Ada Obi"

        # Withdraw 5000 -> 45000
        status, res = app.handle_action("/api/withdraw", {"amount": "5000"})
        assert status == 200 and res["ok"] is True
        assert res["account"]["balance"] == 45000.0
        assert res["info"]["notes"] == {1000: 5}
        assert "PYTHON ATM RECEIPT" in res["info"]["receipt_text"]

        # Admin overview requires auth first
        status, _ = app.get_admin_overview()
        assert status == 403

        status, res = app.handle_action("/api/admin/login", {"pin": "0000"})
        assert status == 200 and res["ok"] is True
        status, overview = app.get_admin_overview()
        assert status == 200 and overview["ok"] is True
        assert overview["statistics"]["total_transactions"] == 1

        print("[PASS] test_web_app_flow")


if __name__ == "__main__":
    test_web_app_flow()
    print("All web backend tests passed!")
