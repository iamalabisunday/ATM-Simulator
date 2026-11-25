"""
ATM Simulator - Beginner-Friendly Single-File Version

This file combines the useful Python parts of the original project:
main.py, models.py, storage.py, and ui.py.

How to run:
    python3 ATM_Simulator_Beginner.py

The original project files are not changed.
"""

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

DATA_FILE = "beginner_data.json"
RECEIPT_FOLDER = "beginner_receipts"
DEFAULT_ADMIN_PIN = "0000"


# ------------------------------------------------------------
# SECTION 1: Small storage and password functions
# ------------------------------------------------------------


def hash_pin(pin):
    """Turn a PIN into a SHA-256 text value so the real PIN is not stored."""
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def load_data():
    """Load saved ATM data. Return None if no usable file exists."""
    path = Path(DATA_FILE)

    if not path.exists():
        print("No saved data found. Creating default accounts.")
        return None

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if "accounts" not in data:
            print("Saved data has the wrong format. Creating default accounts.")
            return None

        return data

    except json.JSONDecodeError:
        print("Saved data is corrupted. Creating default accounts.")
        return None
    except OSError as error:
        print("Could not read saved data:", error)
        return None


def save_data(atm):
    """Save the admin PIN, notes and accounts to a JSON file."""
    accounts_data = {}

    for account_number, account in atm.accounts.items():
        accounts_data[account_number] = account.to_dict()

    data = {
        "admin_pin_hash": atm.admin_pin_hash,
        "notes": atm.notes,
        "accounts": accounts_data,
    }

    with Path(DATA_FILE).open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def save_receipt(account, action, amount, extra_line=""):
    """Create and save a simple text receipt."""
    receipt_folder = Path(RECEIPT_FOLDER)
    receipt_folder.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "========================================",
        "             ATM RECEIPT",
        "========================================",
        "Date/Time: " + timestamp,
        "Account: " + account.account_number,
        "Owner: " + account.owner,
        "Action: " + action,
        "Amount: " + format_money(amount),
        "New balance: " + format_money(account.balance),
    ]

    if extra_line:
        lines.append(extra_line)

    lines.append("========================================")

    receipt_text = "\n".join(lines)

    filename_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = "receipt_{}_{}.txt".format(
        account.account_number, filename_timestamp
    )
    receipt_path = receipt_folder / filename
    receipt_path.write_text(receipt_text, encoding="utf-8")

    return receipt_text, str(receipt_path)


def format_money(amount):
    """Format an amount for printing, for example 50000 becomes 50,000.00."""
    return "{:,.2f}".format(amount)


# ------------------------------------------------------------
# SECTION 2: Account classes
# ------------------------------------------------------------


class Account:
    """A basic bank account."""

    def __init__(
        self,
        account_number,
        owner,
        pin,
        balance=0,
        failed_attempts=0,
        is_blocked=False,
        transactions=None,
        daily_withdrawn=0,
        last_withdrawal_date="",
    ):
        self.account_number = str(account_number)
        self.owner = owner
        self.pin_hash = hash_pin(pin)
        self.balance = round(float(balance), 2)
        self.failed_attempts = failed_attempts
        self.is_blocked = is_blocked
        self.transactions = transactions if transactions is not None else []
        self.daily_withdrawn = round(float(daily_withdrawn), 2)
        self.last_withdrawal_date = last_withdrawal_date

        self.per_transaction_limit = 20000
        self.daily_limit = 50000
        self.minimum_balance = 1000

    def account_type(self):
        return "Standard"

    def verify_pin(self, pin):
        return hash_pin(pin) == self.pin_hash

    def change_pin(self, old_pin, new_pin):
        if not self.verify_pin(old_pin):
            return False, "The old PIN is incorrect."

        if not (new_pin.isdigit() and len(new_pin) == 4):
            return False, "The new PIN must contain exactly 4 digits."

        if new_pin == old_pin:
            return False, "The new PIN must be different."

        self.pin_hash = hash_pin(new_pin)
        return True, "PIN changed successfully."

    def record_transaction(self, transaction_type, amount, details=""):
        """Add a transaction to this account's history."""
        transaction = {
            "type": transaction_type,
            "amount": round(float(amount), 2),
            "balance_after": round(self.balance, 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "details": details,
        }
        self.transactions.append(transaction)

    def mini_statement(self, count=5):
        """Return only the most recent transactions."""
        return self.transactions[-count:]

    def deposit(self, amount):
        if amount <= 0:
            return False, "Deposit amount must be greater than zero."

        self.balance = round(self.balance + amount, 2)
        self.record_transaction("deposit", amount)
        return True, "Deposit successful."

    def reset_daily_limit_if_new_day(self):
        today = date.today().isoformat()
        if self.last_withdrawal_date != today:
            self.daily_withdrawn = 0
            self.last_withdrawal_date = today

    def minimum_allowed_balance(self):
        return self.minimum_balance

    def can_withdraw(self, amount):
        if amount <= 0:
            return False, "Withdrawal amount must be greater than zero."

        if amount > self.per_transaction_limit:
            return False, "Amount exceeds the per-transaction limit of 20,000."

        self.reset_daily_limit_if_new_day()

        if self.daily_withdrawn + amount > self.daily_limit:
            return False, "This would exceed today's 50,000 daily limit."

        if self.balance - amount < self.minimum_allowed_balance():
            return False, "You must keep at least 1,000 in your account."

        return True, "Withdrawal is allowed."

    def withdraw(self, amount):
        allowed, message = self.can_withdraw(amount)

        if not allowed:
            return False, message

        self.balance = round(self.balance - amount, 2)
        self.daily_withdrawn = round(self.daily_withdrawn + amount, 2)
        self.last_withdrawal_date = date.today().isoformat()
        self.record_transaction("withdrawal", amount)

        return True, "Withdrawal successful."

    def transfer(self, target_account, amount):
        if target_account is None:
            return False, "The recipient account was not found."

        if target_account.account_number == self.account_number:
            return False, "You cannot transfer to the same account."

        if amount <= 0:
            return False, "Transfer amount must be greater than zero."

        if self.balance - amount < self.minimum_allowed_balance():
            return False, "You cannot transfer below your minimum balance."

        self.balance = round(self.balance - amount, 2)
        target_account.balance = round(target_account.balance + amount, 2)

        self.record_transaction(
            "transfer_out", amount,
            "To " + target_account.account_number
        )
        target_account.record_transaction(
            "transfer_in", amount,
            "From " + self.account_number
        )

        return True, "Transfer successful."

    def to_dict(self):
        """Turn this account into a dictionary for JSON storage."""
        return {
            "account_type": self.account_type(),
            "account_number": self.account_number,
            "owner": self.owner,
            "pin_hash": self.pin_hash,
            "balance": self.balance,
            "failed_attempts": self.failed_attempts,
            "is_blocked": self.is_blocked,
            "transactions": self.transactions,
            "daily_withdrawn": self.daily_withdrawn,
            "last_withdrawal_date": self.last_withdrawal_date,
        }


class SavingsAccount(Account):
    """A Standard account plus savings interest and monthly limits."""

    def __init__(self, account_number, owner, pin, balance=0, **saved_values):
        monthly_withdrawals = saved_values.pop("monthly_withdrawals", 0)
        last_withdrawal_month = saved_values.pop("last_withdrawal_month", "")
        super().__init__(account_number, owner, pin, balance, **saved_values)
        self.interest_rate = 0.03
        self.monthly_withdrawal_limit = 4
        self.monthly_withdrawals = monthly_withdrawals
        self.last_withdrawal_month = last_withdrawal_month

    def account_type(self):
        return "Savings"

    def can_withdraw(self, amount):
        today = date.today()
        month = today.strftime("%Y-%m")

        if self.last_withdrawal_month != month:
            self.monthly_withdrawals = 0
            self.last_withdrawal_month = month

        if self.monthly_withdrawals >= self.monthly_withdrawal_limit:
            return False, "The Savings account has reached its 4-withdrawal monthly limit."

        return super().can_withdraw(amount)

    def withdraw(self, amount):
        allowed, message = super().withdraw(amount)

        if allowed:
            self.monthly_withdrawals += 1
            self.last_withdrawal_month = date.today().strftime("%Y-%m")

        return allowed, message

    def apply_interest(self):
        if self.balance <= 0:
            return False, "There is no positive balance for interest."

        interest = round(self.balance * self.interest_rate, 2)
        if interest <= 0:
            return False, "The interest amount is too small."

        self.balance = round(self.balance + interest, 2)
        self.record_transaction("interest", interest, "Interest at 3%")
        return True, "Interest added successfully."

    def to_dict(self):
        data = super().to_dict()
        data["interest_rate"] = self.interest_rate
        data["monthly_withdrawal_limit"] = self.monthly_withdrawal_limit
        data["monthly_withdrawals"] = self.monthly_withdrawals
        data["last_withdrawal_month"] = self.last_withdrawal_month
        return data


class CurrentAccount(Account):
    """A bank account that can use an overdraft."""

    def __init__(self, account_number, owner, pin, balance=0, **saved_values):
        overdraft_limit = saved_values.pop("overdraft_limit", 10000)
        super().__init__(account_number, owner, pin, balance, **saved_values)
        self.overdraft_limit = overdraft_limit

    def account_type(self):
        return "Current"

    def minimum_allowed_balance(self):
        return -self.overdraft_limit

    def to_dict(self):
        data = super().to_dict()
        data["overdraft_limit"] = self.overdraft_limit
        return data


# ------------------------------------------------------------
# SECTION 3: ATM cash dispenser
# ------------------------------------------------------------


class NoteDispenser:
    """Stores ATM cash and searches for an exact combination of notes."""

    def __init__(self, notes=None):
        self.notes = notes if notes is not None else {
            1000: 60,
            500: 40,
            200: 25,
            100: 50,
        }

    def total_cash(self):
        total = 0
        for denomination, count in self.notes.items():
            total += denomination * count
        return total

    def find_notes(self, amount):
        """Try to make an exact amount using the available notes."""
        if amount <= 0 or amount != int(amount):
            return None

        target = int(amount)

        if target > self.total_cash():
            return None

        denominations = sorted(self.notes.keys(), reverse=True)

        def search(index, remaining):
            if remaining == 0:
                return {}

            if index >= len(denominations):
                return None

            denomination = denominations[index]
            maximum_count = min(
                self.notes[denomination],
                remaining // denomination
            )

            for count in range(maximum_count, -1, -1):
                result = search(index + 1, remaining - count * denomination)

                if result is not None:
                    if count > 0:
                        result[denomination] = count
                    return result

            return None

        return search(0, target)

    def restock(self, denomination, count):
        if denomination not in self.notes:
            return False, "This denomination is not supported."

        if count <= 0:
            return False, "The note count must be greater than zero."

        self.notes[denomination] += count
        return True, "ATM restocked successfully."


# ------------------------------------------------------------
# SECTION 4: ATM controller
# ------------------------------------------------------------


class ATM:
    """Coordinates accounts, login, cash, saving and admin operations."""

    MAX_PIN_ATTEMPTS = 3

    def __init__(self):
        self.current_account = None
        self.admin_pin_hash = hash_pin(DEFAULT_ADMIN_PIN)

        saved_data = load_data()

        if saved_data is None:
            self.accounts = self.create_default_accounts()
            self.notes = {1000: 60, 500: 40, 200: 25, 100: 50}
            self.dispenser = NoteDispenser(self.notes)
            save_data(self)
        else:
            self.admin_pin_hash = saved_data.get("admin_pin_hash", hash_pin(DEFAULT_ADMIN_PIN))
            self.notes = {
                int(denomination): int(count)
                for denomination, count in saved_data.get("notes", {}).items()
            }
            self.dispenser = NoteDispenser(self.notes)

            self.accounts = {}
            for account_number, saved_account in saved_data["accounts"].items():
                account = self.create_account_from_saved_data(saved_account)
                self.accounts[account_number] = account

    def create_default_accounts(self):
        return {
            "1001": SavingsAccount("1001", "Ada Obi", "4321", 50000),
            "1002": CurrentAccount("1002", "Chidi Eze", "1234", 25000, overdraft_limit=10000),
            "1003": SavingsAccount("1003", "Zainab Bello", "5678", 80000),
            "1004": Account("1004", "Tunde Bakare", "2468", 15000),
        }

    def create_account_from_saved_data(self, saved_account):
        account_type = saved_account.get("account_type", "Standard")
        account_number = saved_account["account_number"]
        owner = saved_account["owner"]

        common_values = {
            "failed_attempts": saved_account.get("failed_attempts", 0),
            "is_blocked": saved_account.get("is_blocked", False),
            "transactions": saved_account.get("transactions", []),
            "daily_withdrawn": saved_account.get("daily_withdrawn", 0),
            "last_withdrawal_date": saved_account.get("last_withdrawal_date", ""),
        }

        pin_hash = saved_account["pin_hash"]

        if account_type == "Savings":
            account = SavingsAccount(
                account_number,
                owner,
                "",
                saved_account.get("balance", 0),
                **common_values,
            )
            account.monthly_withdrawals = saved_account.get("monthly_withdrawals", 0)
            account.last_withdrawal_month = saved_account.get("last_withdrawal_month", "")
        elif account_type == "Current":
            account = CurrentAccount(
                account_number,
                owner,
                "",
                saved_account.get("balance", 0),
                overdraft_limit=saved_account.get("overdraft_limit", 10000),
                **common_values,
            )
        else:
            account = Account(
                account_number,
                owner,
                "",
                saved_account.get("balance", 0),
                **common_values,
            )

        account.pin_hash = pin_hash
        return account

    def login(self, account_number, pin):
        account = self.accounts.get(account_number.strip())

        if account is None:
            return False, "Account number not found."

        if account.is_blocked:
            return False, "This account is blocked. Ask an admin to unblock it."

        if account.verify_pin(pin):
            account.failed_attempts = 0
            self.current_account = account
            save_data(self)
            return True, "Welcome, " + account.owner + "."

        account.failed_attempts += 1
        attempts_left = self.MAX_PIN_ATTEMPTS - account.failed_attempts

        if attempts_left <= 0:
            account.is_blocked = True
            save_data(self)
            return False, "The account is now blocked after 3 failed PIN attempts."

        save_data(self)
        return False, "Incorrect PIN. " + str(attempts_left) + " attempt(s) left."

    def logout(self):
        if self.current_account is None:
            return "No customer is logged in."

        name = self.current_account.owner
        self.current_account = None
        return "Goodbye, " + name + "."

    def deposit(self, amount):
        if self.current_account is None:
            return False, "Please log in first.", None

        allowed, message = self.current_account.deposit(amount)
        if not allowed:
            return False, message, None

        save_data(self)
        receipt_text, receipt_path = save_receipt(
            self.current_account, "Deposit", amount
        )

        info = {
            "receipt_text": receipt_text,
            "receipt_path": receipt_path,
        }
        return True, message, info

    def withdraw(self, amount):
        if self.current_account is None:
            return False, "Please log in first.", None

        allowed, message = self.current_account.can_withdraw(amount)
        if not allowed:
            return False, message, None

        note_plan = self.dispenser.find_notes(amount)
        if note_plan is None:
            return False, "The ATM cannot make that amount with the available notes.", None

        allowed, message = self.current_account.withdraw(amount)
        if not allowed:
            return False, message, None

        for denomination, count in note_plan.items():
            self.notes[denomination] -= count

        save_data(self)
        notes_text = ", ".join(
            str(count) + " x " + format_money(denomination)
            for denomination, count in sorted(note_plan.items(), reverse=True)
        )

        receipt_text, receipt_path = save_receipt(
            self.current_account,
            "Withdrawal",
            amount,
            "Notes: " + notes_text,
        )

        info = {
            "notes": note_plan,
            "receipt_text": receipt_text,
            "receipt_path": receipt_path,
        }
        return True, message, info

    def transfer(self, recipient_number, amount):
        if self.current_account is None:
            return False, "Please log in first.", None

        recipient = self.accounts.get(recipient_number.strip())
        allowed, message = self.current_account.transfer(recipient, amount)

        if not allowed:
            return False, message, None

        save_data(self)
        receipt_text, receipt_path = save_receipt(
            self.current_account,
            "Transfer",
            amount,
            "Recipient: " + recipient.account_number,
        )

        info = {
            "receipt_text": receipt_text,
            "receipt_path": receipt_path,
        }
        return True, message, info

    def change_pin(self, old_pin, new_pin):
        if self.current_account is None:
            return False, "Please log in first."

        allowed, message = self.current_account.change_pin(old_pin, new_pin)
        if allowed:
            save_data(self)
        return allowed, message

    def apply_interest(self):
        if self.current_account is None:
            return False, "Please log in first.", None

        if not isinstance(self.current_account, SavingsAccount):
            return False, "Interest is only for Savings accounts.", None

        balance_before = self.current_account.balance
        allowed, message = self.current_account.apply_interest()
        if not allowed:
            return False, message, None

        interest_amount = round(
            self.current_account.balance - balance_before,
            2,
        )
        save_data(self)
        receipt_text, receipt_path = save_receipt(
            self.current_account,
            "Interest",
            interest_amount,
        )

        info = {
            "receipt_text": receipt_text,
            "receipt_path": receipt_path,
        }
        return True, message, info

    def verify_admin_pin(self, pin):
        return hash_pin(pin) == self.admin_pin_hash

    def create_account(self, account_number, owner, pin, account_type, balance):
        account_number = account_number.strip()
        owner = owner.strip()

        if account_number in self.accounts:
            return False, "That account number already exists."

        if not owner:
            return False, "Owner name cannot be empty."

        if not (pin.isdigit() and len(pin) == 4):
            return False, "PIN must contain exactly 4 digits."

        if balance < 0:
            return False, "Initial balance cannot be negative."

        if account_type == "Savings":
            account = SavingsAccount(account_number, owner, pin, balance)
        elif account_type == "Current":
            account = CurrentAccount(account_number, owner, pin, balance, overdraft_limit=10000)
        else:
            account = Account(account_number, owner, pin, balance)

        self.accounts[account_number] = account
        save_data(self)
        return True, account_type + " account created."

    def unblock_account(self, account_number):
        account = self.accounts.get(account_number.strip())

        if account is None:
            return False, "Account not found."

        account.is_blocked = False
        account.failed_attempts = 0
        save_data(self)
        return True, "Account has been unblocked."


# ------------------------------------------------------------
# SECTION 5: Beginner-friendly text menus
# ------------------------------------------------------------


def ask_number(prompt):
    """Ask for a number without crashing on text input."""
    text = input(prompt).strip().replace(",", "")

    try:
        return float(text)
    except ValueError:
        print("Please enter a valid number.")
        return None


def print_accounts(atm):
    print("\n--- Accounts ---")
    print("Account  Owner              Type      Balance       Status")

    for account in atm.accounts.values():
        status = "BLOCKED" if account.is_blocked else "Active"
        print(
            account.account_number,
            account.owner,
            account.account_type(),
            format_money(account.balance),
            status,
        )


def print_mini_statement(account):
    print("\n--- Mini Statement ---")
    transactions = account.mini_statement()

    if not transactions:
        print("No transactions yet.")
        return

    for transaction in transactions:
        print(
            transaction["timestamp"],
            transaction["type"],
            format_money(transaction["amount"]),
            "Balance:",
            format_money(transaction["balance_after"]),
        )


def customer_menu(atm):
    while atm.current_account is not None:
        account = atm.current_account

        print("\n--- Customer Menu ---")
        print("Account:", account.owner, "(" + account.account_type() + ")")
        print("1. Check balance")
        print("2. Deposit")
        print("3. Withdraw")
        print("4. Transfer")
        print("5. Mini statement")
        print("6. Change PIN")
        print("7. Apply Savings interest")
        print("8. Logout")

        choice = input("Choose 1-8: ").strip()

        if choice == "1":
            print("Balance:", format_money(account.balance))

        elif choice == "2":
            amount = ask_number("Deposit amount: ")
            if amount is not None:
                allowed, message, info = atm.deposit(amount)
                print(message)
                if allowed:
                    print("Receipt:", info["receipt_path"])

        elif choice == "3":
            amount = ask_number("Withdrawal amount: ")
            if amount is not None:
                allowed, message, info = atm.withdraw(amount)
                print(message)
                if allowed:
                    print("Balance:", format_money(account.balance))
                    print("Notes:", info["notes"])
                    print("Receipt:", info["receipt_path"])

        elif choice == "4":
            recipient = input("Recipient account number: ").strip()
            amount = ask_number("Transfer amount: ")
            if amount is not None:
                allowed, message, info = atm.transfer(recipient, amount)
                print(message)
                if allowed:
                    print("Receipt:", info["receipt_path"])

        elif choice == "5":
            print_mini_statement(account)

        elif choice == "6":
            old_pin = input("Current PIN: ").strip()
            new_pin = input("New 4-digit PIN: ").strip()
            allowed, message = atm.change_pin(old_pin, new_pin)
            print(message)

        elif choice == "7":
            allowed, message, info = atm.apply_interest()
            print(message)

        elif choice == "8":
            print(atm.logout())

        else:
            print("Please choose a number from 1 to 8.")


def admin_menu(atm):
    pin = input("Admin PIN (default 0000): ").strip()

    if not atm.verify_admin_pin(pin):
        print("Incorrect admin PIN.")
        return

    print("Admin login successful.")

    while True:
        print("\n--- Admin Menu ---")
        print("1. View accounts")
        print("2. Create account")
        print("3. Unblock account")
        print("4. View ATM cash")
        print("5. Restock ATM")
        print("6. Exit admin mode")

        choice = input("Choose 1-6: ").strip()

        if choice == "1":
            print_accounts(atm)

        elif choice == "2":
            account_number = input("Account number: ").strip()
            owner = input("Owner name: ").strip()
            pin = input("4-digit PIN: ").strip()
            account_type = input("Type (Savings, Current, Standard): ").strip()

            if account_type not in ("Savings", "Current", "Standard"):
                account_type = "Standard"

            balance = ask_number("Initial balance: ")
            if balance is not None:
                allowed, message = atm.create_account(
                    account_number,
                    owner,
                    pin,
                    account_type,
                    balance,
                )
                print(message)

        elif choice == "3":
            account_number = input("Account number to unblock: ").strip()
            allowed, message = atm.unblock_account(account_number)
            print(message)

        elif choice == "4":
            print("ATM cash left:", format_money(atm.dispenser.total_cash()))
            for denomination, count in sorted(atm.notes.items(), reverse=True):
                print(
                    denomination,
                    "naira:",
                    count,
                    "notes",
                )

        elif choice == "5":
            denomination = ask_number("Denomination (100, 200, 500 or 1000): ")
            count = ask_number("Number of notes: ")

            if denomination is not None and count is not None:
                allowed, message = atm.dispenser.restock(
                    int(denomination), int(count)
                )
                if allowed:
                    save_data(atm)
                print(message)

        elif choice == "6":
            print("Leaving admin mode.")
            break

        else:
            print("Please choose a number from 1 to 6.")


# ------------------------------------------------------------
# SECTION 6: Main program
# ------------------------------------------------------------


def main():
    """Start the ATM simulator."""
    atm = ATM()

    print("========================================")
    print("       Beginner Python ATM")
    print("========================================")

    while True:
        print("\n--- Main Menu ---")
        print("1. Customer login")
        print("2. Admin mode")
        print("3. Exit")

        choice = input("Choose 1-3: ").strip()

        if choice == "1":
            account_number = input("Account number: ").strip()
            pin = input("PIN: ").strip()

            allowed, message = atm.login(account_number, pin)
            print(message)

            if allowed:
                customer_menu(atm)

        elif choice == "2":
            admin_menu(atm)

        elif choice == "3":
            print("Thank you for using the ATM.")
            break

        else:
            print("Please choose a number from 1 to 3.")


if __name__ == "__main__":
    main()
