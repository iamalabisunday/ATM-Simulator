"""
tests.py — Member C (Self-Tests)
Assert-based tests covering login, blocking, limits, transfers,
note dispensing, inheritance, PIN hashing, JSON error handling, and statistics.
Run with: python3 tests.py
"""

from pathlib import Path
import tempfile

from models import ATM, CurrentAccount, NoteDispenser, SavingsAccount
from storage import hash_pin


def make_temp_atm(tmp_dir: str) -> ATM:
    """Create an isolated ATM instance backed by a temporary directory."""
    data_file = str(Path(tmp_dir) / "atm_data.json")
    receipt_dir = str(Path(tmp_dir) / "receipts")
    return ATM(data_file=data_file, receipt_dir=receipt_dir)


def test_login_and_blocking() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        atm = make_temp_atm(tmp)

        ok, msg = atm.login("1001", "4321")
        assert ok is True, msg
        assert "Ada Obi" in msg
        atm.logout()

        # 3 wrong attempts should block account 1001
        for attempt in range(2):
            ok, msg = atm.login("1001", "0000")
            assert ok is False
            assert "remaining" in msg.lower()

        ok, msg = atm.login("1001", "0000")
        assert ok is False
        assert "blocked" in msg.lower()
        assert atm.accounts["1001"].is_blocked is True

        # Even correct PIN fails while blocked
        ok, _ = atm.login("1001", "4321")
        assert ok is False

        # Admin unblocks account
        assert atm.verify_admin_pin("0000") is True
        ok, _ = atm.admin_unblock_account("1001")
        assert ok is True
        assert atm.accounts["1001"].is_blocked is False

        ok, _ = atm.login("1001", "4321")
        assert ok is True


def test_deposit_withdraw_and_example_case() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        atm = make_temp_atm(tmp)
        atm.login("1001", "4321")

        # Reject zero / negative amounts
        ok, _, _ = atm.deposit(0)
        assert ok is False
        ok, _, _ = atm.deposit(-500)
        assert ok is False
        ok, _, _ = atm.withdraw(-100)
        assert ok is False

        # Example Input: withdraw 5000 from 50,000 -> 45,000
        ok, msg, info = atm.withdraw(5000)
        assert ok is True, msg
        assert info is not None
        assert info["balance"] == 45000.0
        assert Path(info["receipt_path"]).exists()

        # Reject withdrawal larger than balance
        ok, _, _ = atm.withdraw(100000)
        assert ok is False


def test_per_tx_min_balance_and_daily_limit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        atm = make_temp_atm(tmp)
        atm.login("1003", "5678")  # Zainab Bello, balance 80,000

        # Exceeds per-tx limit (20,000)
        ok, msg, _ = atm.withdraw(25000, today_str="2026-11-25")
        assert ok is False
        assert "per-transaction limit" in msg.lower()

        # Three valid withdrawals on same day -> total 50,000 (hits daily limit)
        assert atm.withdraw(20000, today_str="2026-11-25")[0] is True
        assert atm.withdraw(20000, today_str="2026-11-25")[0] is True
        assert atm.withdraw(10000, today_str="2026-11-25")[0] is True

        # Next withdrawal same day exceeds daily limit of 50,000
        ok, msg, _ = atm.withdraw(1000, today_str="2026-11-25")
        assert ok is False
        assert "daily withdrawal limit" in msg.lower()

        # New date resets daily withdrawal limit
        ok, _, _ = atm.withdraw(1000, today_str="2026-11-26")
        assert ok is True


def test_minimum_balance_rule() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        atm = make_temp_atm(tmp)
        atm.login("1004", "2468")  # Tunde Bakare, Standard account, balance 15,000, min_balance 1,000

        # Trying to withdraw 14,500 leaves 500 < 1,000 -> rejected
        ok, msg, _ = atm.withdraw(14500)
        assert ok is False
        assert "minimum balance" in msg.lower()

        # Withdrawing 14,000 leaves exactly 1,000 -> allowed
        ok, _, info = atm.withdraw(14000)
        assert ok is True
        assert info is not None and info["balance"] == 1000.0


def test_transfers() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        atm = make_temp_atm(tmp)
        atm.login("1001", "4321")  # 50,000

        # Missing recipient rejected
        ok, msg, _ = atm.transfer("9999", 1000)
        assert ok is False
        assert "does not exist" in msg.lower()

        # Self transfer rejected
        ok, _, _ = atm.transfer("1001", 1000)
        assert ok is False

        # Valid transfer to 1002 (25,000)
        ok, _, info = atm.transfer("1002", 5000)
        assert ok is True
        assert info is not None and info["balance"] == 45000.0
        assert atm.accounts["1002"].balance == 30000.0


def test_note_dispensing_and_exact_change() -> None:
    # Tricky non-greedy case: 600 with 1x500 and 3x200 must pick 3x200
    dispenser = NoteDispenser({500: 1, 200: 3})
    plan = dispenser.dispense(600)
    assert plan == {200: 3}, f"Expected {{200: 3}}, got {plan}"
    assert dispenser.total_cash() == 500

    # Impossible exact payout (e.g. 150 with only 500 remaining)
    assert dispenser.calculate_notes(150) is None
    assert dispenser.dispense(150) is None

    # ATM refuses withdrawal if notes cannot make exact amount (e.g. 50)
    with tempfile.TemporaryDirectory() as tmp:
        atm = make_temp_atm(tmp)
        atm.login("1001", "4321")
        before = atm.check_balance()
        ok, msg, _ = atm.withdraw(50)
        assert ok is False
        assert "exact amount" in msg.lower()
        assert atm.check_balance() == before


def test_inheritance_savings_and_current() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        atm = make_temp_atm(tmp)

        # SavingsAccount: interest + monthly withdrawal limit (4)
        savings = atm.accounts["1001"]
        assert isinstance(savings, SavingsAccount)
        atm.login("1001", "4321")
        for _ in range(4):
            assert atm.withdraw(1000, today_str="2026-11-01")[0] is True
        ok, msg, _ = atm.withdraw(1000, today_str="2026-11-02")
        assert ok is False
        assert "monthly withdrawal limit" in msg.lower()

        before = atm.check_balance()
        ok, _, _ = atm.apply_interest_current()
        assert ok is True
        assert atm.check_balance() > before
        atm.logout()

        # CurrentAccount: allows overdraft up to 10,000
        current = atm.accounts["1002"]
        assert isinstance(current, CurrentAccount)
        atm.login("1002", "1234")
        assert atm.withdraw(20000, today_str="2026-11-01")[0] is True
        assert atm.withdraw(10000, today_str="2026-11-01")[0] is True  # balance now -5,000
        assert atm.check_balance() == -5000.0
        # Overdraft limit is 10,000 so withdrawing 6,000 (would be -11,000) fails
        ok, _, _ = atm.withdraw(6000, today_str="2026-11-01")
        assert ok is False


def test_pin_change_hashing_and_persistence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_file = Path(tmp) / "atm_data.json"
        atm = ATM(data_file=str(data_file), receipt_dir=str(Path(tmp) / "receipts"))
        atm.login("1001", "4321")

        # Wrong old PIN fails
        ok, _ = atm.change_pin("9999", "8888")
        assert ok is False

        # Valid change succeeds and hashes PIN
        ok, _ = atm.change_pin("4321", "8888")
        assert ok is True
        raw_json = data_file.read_text(encoding="utf-8")
        assert "8888" not in raw_json  # Plain-text PIN is never stored
        assert hash_pin("8888") in raw_json

        # Reload from disk and verify new PIN works
        reloaded = ATM(data_file=str(data_file), receipt_dir=str(Path(tmp) / "receipts"))
        assert reloaded.login("1001", "4321")[0] is False
        reloaded.accounts["1001"].failed_attempts = 0
        assert reloaded.login("1001", "8888")[0] is True


def test_corrupted_and_empty_json_handling() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_file = Path(tmp) / "atm_data.json"
        receipt_dir = str(Path(tmp) / "receipts")

        # Empty file
        data_file.write_text("", encoding="utf-8")
        atm_empty = ATM(data_file=str(data_file), receipt_dir=receipt_dir)
        assert atm_empty.startup_message is not None
        assert "empty" in atm_empty.startup_message.lower()
        assert "1001" in atm_empty.accounts

        # Corrupted JSON
        data_file.write_text("{broken json!!!", encoding="utf-8")
        atm_bad = ATM(data_file=str(data_file), receipt_dir=receipt_dir)
        assert atm_bad.startup_message is not None
        assert "corrupted" in atm_bad.startup_message.lower()
        assert "1001" in atm_bad.accounts


def test_admin_create_account_and_statistics() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        atm = make_temp_atm(tmp)
        ok, _ = atm.admin_create_account("1005", "Ngozi Nnamdi", "7777", 12000.0, "Current")
        assert ok is True
        assert isinstance(atm.accounts["1005"], CurrentAccount)

        atm.login("1005", "7777")
        atm.deposit(8000)
        atm.withdraw(3000)
        stats = atm.get_statistics()
        assert stats["total_transactions"] == 2
        assert stats["counts_by_type"]["deposit"] == 1
        assert stats["counts_by_type"]["withdrawal"] == 1
        assert stats["largest_deposit"][0] == 8000.0
        assert stats["largest_withdrawal"][0] == 3000.0
        assert stats["busiest_hour"] is not None


def run_all_tests() -> None:
    tests = [
        test_login_and_blocking,
        test_deposit_withdraw_and_example_case,
        test_per_tx_min_balance_and_daily_limit,
        test_minimum_balance_rule,
        test_transfers,
        test_note_dispensing_and_exact_change,
        test_inheritance_savings_and_current,
        test_pin_change_hashing_and_persistence,
        test_corrupted_and_empty_json_handling,
        test_admin_create_account_and_statistics,
    ]
    for fn in tests:
        fn()
        print(f"[PASS] {fn.__name__}")
    print(f"\nAll {len(tests)} tests passed successfully!")


if __name__ == "__main__":
    run_all_tests()
