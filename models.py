"""
models.py — Member A (Core Classes & Rules)
Defines Account, SavingsAccount, CurrentAccount, NoteDispenser, and ATM.
"""

from datetime import date, datetime

from storage import compute_statistics, hash_pin, load_data, save_data, save_receipt

DEFAULT_ADMIN_PIN = "0000"
DEFAULT_NOTES = {1000: 60, 500: 40, 200: 25, 100: 50}


class Account:
    """Base bank account class supporting deposits, withdrawals, transfers, and PIN checks."""

    def __init__(
        self,
        account_number: str,
        owner: str,
        pin_hash: str,
        balance: float = 0.0,
        transactions: list[dict] | None = None,
        failed_attempts: int = 0,
        is_blocked: bool = False,
        daily_withdrawn: float = 0.0,
        last_withdrawal_date: str = "",
        per_tx_limit: float = 20000.0,
        daily_limit: float = 50000.0,
        min_balance: float = 1000.0,
    ) -> None:
        self.account_number = str(account_number)
        self.owner = owner
        self.pin_hash = pin_hash
        self.balance = round(float(balance), 2)
        self.transactions = list(transactions) if transactions else []
        self.failed_attempts = int(failed_attempts)
        self.is_blocked = bool(is_blocked)
        self.daily_withdrawn = round(float(daily_withdrawn), 2)
        self.last_withdrawal_date = last_withdrawal_date
        self.per_tx_limit = float(per_tx_limit)
        self.daily_limit = float(daily_limit)
        self.min_balance = float(min_balance)

    def account_type(self) -> str:
        """Return human-readable account type name."""
        return "Standard"

    def _minimum_allowed_balance(self) -> float:
        """Return the lowest balance permitted after a withdrawal or transfer."""
        return self.min_balance

    def verify_pin(self, pin: str) -> bool:
        """Check whether the provided plain-text PIN matches the stored hash."""
        return hash_pin(pin) == self.pin_hash

    def change_pin(self, old_pin: str, new_pin: str) -> tuple[bool, str]:
        """Change the account PIN after verifying the old PIN."""
        if not self.verify_pin(old_pin):
            return False, "Current PIN is incorrect."
        new_pin = new_pin.strip()
        if not (new_pin.isdigit() and len(new_pin) == 4):
            return False, "New PIN must be exactly 4 digits."
        if new_pin == old_pin.strip():
            return False, "New PIN must be different from your current PIN."
        self.pin_hash = hash_pin(new_pin)
        return True, "PIN changed successfully."

    def check_balance(self) -> float:
        """Return the current account balance."""
        return self.balance

    def _reset_daily_if_needed(self, today_str: str) -> None:
        """Reset the daily withdrawal total when the calendar date changes."""
        if self.last_withdrawal_date != today_str:
            self.daily_withdrawn = 0.0
            self.last_withdrawal_date = today_str

    def record_transaction(self, tx_type: str, amount: float, details: str = "") -> dict:
        """Append a timestamped transaction entry and return it."""
        entry = {
            "type": tx_type,
            "amount": round(float(amount), 2),
            "balance_after": round(self.balance, 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "details": details,
        }
        self.transactions.append(entry)
        return entry

    def mini_statement(self, count: int = 5) -> list[dict]:
        """Return up to the last `count` transactions (oldest to newest)."""
        return self.transactions[-count:]

    def deposit(self, amount: float, details: str = "Cash deposit") -> tuple[bool, str]:
        """Add a positive amount to the account balance."""
        if amount <= 0:
            return False, "Deposit amount must be greater than zero."
        self.balance = round(self.balance + amount, 2)
        self.record_transaction("deposit", amount, details)
        return True, "Deposit successful."

    def can_withdraw(self, amount: float, today_str: str | None = None) -> tuple[bool, str]:
        """Validate withdrawal amount against balance, minimum balance, and limits."""
        if amount <= 0:
            return False, "Withdrawal amount must be greater than zero."
        if amount > self.per_tx_limit:
            return (
                False,
                f"Amount exceeds per-transaction limit of {self.per_tx_limit:,.2f}.",
            )

        today_str = today_str or date.today().isoformat()
        self._reset_daily_if_needed(today_str)

        if self.daily_withdrawn + amount > self.daily_limit:
            remaining = max(0.0, self.daily_limit - self.daily_withdrawn)
            return (
                False,
                f"Daily withdrawal limit ({self.daily_limit:,.2f}) exceeded. "
                f"Remaining today: {remaining:,.2f}.",
            )

        floor = self._minimum_allowed_balance()
        if self.balance - amount < floor:
            if floor > 0:
                return (
                    False,
                    f"Insufficient funds. A minimum balance of {floor:,.2f} must remain.",
                )
            return False, "Insufficient funds for this withdrawal."

        return True, "OK"

    def withdraw(
        self,
        amount: float,
        details: str = "Cash withdrawal",
        today_str: str | None = None,
    ) -> tuple[bool, str]:
        """Deduct a valid withdrawal amount and record the transaction."""
        today_str = today_str or date.today().isoformat()
        ok, msg = self.can_withdraw(amount, today_str=today_str)
        if not ok:
            return False, msg

        self.balance = round(self.balance - amount, 2)
        self.daily_withdrawn = round(self.daily_withdrawn + amount, 2)
        self.last_withdrawal_date = today_str
        self.record_transaction("withdrawal", amount, details)
        return True, "Withdrawal successful. Please take your cash."

    def transfer(self, to_account: "Account", amount: float) -> tuple[bool, str]:
        """Transfer money from this account to another Account object."""
        if to_account is None:
            return False, "Receiving account does not exist."
        if to_account.account_number == self.account_number:
            return False, "Cannot transfer to the same account."
        if amount <= 0:
            return False, "Transfer amount must be greater than zero."

        floor = self._minimum_allowed_balance()
        if self.balance - amount < floor:
            if floor > 0:
                return (
                    False,
                    f"Insufficient funds. A minimum balance of {floor:,.2f} must remain.",
                )
            return False, "Insufficient funds for this transfer."

        self.balance = round(self.balance - amount, 2)
        to_account.balance = round(to_account.balance + amount, 2)

        self.record_transaction(
            "transfer_out", amount, f"To {to_account.account_number} ({to_account.owner})"
        )
        to_account.record_transaction(
            "transfer_in", amount, f"From {self.account_number} ({self.owner})"
        )
        return True, f"Transferred {amount:,.2f} to {to_account.owner}."

    def to_dict(self) -> dict:
        """Serialize account state to a JSON-friendly dictionary."""
        return {
            "account_class": self.account_type(),
            "account_number": self.account_number,
            "owner": self.owner,
            "pin_hash": self.pin_hash,
            "balance": self.balance,
            "transactions": self.transactions,
            "failed_attempts": self.failed_attempts,
            "is_blocked": self.is_blocked,
            "daily_withdrawn": self.daily_withdrawn,
            "last_withdrawal_date": self.last_withdrawal_date,
            "per_tx_limit": self.per_tx_limit,
            "daily_limit": self.daily_limit,
            "min_balance": self.min_balance,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Account":
        """Reconstruct an Account instance from saved dictionary data."""
        return cls(
            account_number=data["account_number"],
            owner=data["owner"],
            pin_hash=data["pin_hash"],
            balance=data.get("balance", 0.0),
            transactions=data.get("transactions", []),
            failed_attempts=data.get("failed_attempts", 0),
            is_blocked=data.get("is_blocked", False),
            daily_withdrawn=data.get("daily_withdrawn", 0.0),
            last_withdrawal_date=data.get("last_withdrawal_date", ""),
            per_tx_limit=data.get("per_tx_limit", 20000.0),
            daily_limit=data.get("daily_limit", 50000.0),
            min_balance=data.get("min_balance", 1000.0),
        )


class SavingsAccount(Account):
    """Savings account that earns interest and caps withdrawals per month."""

    def __init__(
        self,
        *args,
        interest_rate: float = 0.03,
        monthly_withdrawal_limit: int = 4,
        monthly_withdrawals: int = 0,
        last_withdrawal_month: str = "",
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.interest_rate = float(interest_rate)
        self.monthly_withdrawal_limit = int(monthly_withdrawal_limit)
        self.monthly_withdrawals = int(monthly_withdrawals)
        self.last_withdrawal_month = last_withdrawal_month

    def account_type(self) -> str:
        return "Savings"

    def _reset_monthly_if_needed(self, month_str: str) -> None:
        if self.last_withdrawal_month != month_str:
            self.monthly_withdrawals = 0
            self.last_withdrawal_month = month_str

    def can_withdraw(self, amount: float, today_str: str | None = None) -> tuple[bool, str]:
        today_str = today_str or date.today().isoformat()
        month_str = today_str[:7]
        self._reset_monthly_if_needed(month_str)

        if self.monthly_withdrawals >= self.monthly_withdrawal_limit:
            return (
                False,
                f"Monthly withdrawal limit ({self.monthly_withdrawal_limit}) reached for Savings account.",
            )
        return super().can_withdraw(amount, today_str=today_str)

    def withdraw(
        self,
        amount: float,
        details: str = "Cash withdrawal",
        today_str: str | None = None,
    ) -> tuple[bool, str]:
        today_str = today_str or date.today().isoformat()
        ok, msg = super().withdraw(amount, details=details, today_str=today_str)
        if ok:
            self.monthly_withdrawals += 1
            self.last_withdrawal_month = today_str[:7]
        return ok, msg

    def apply_interest(self) -> tuple[bool, str]:
        """Credit interest based on current balance."""
        if self.balance <= 0:
            return False, "No positive balance to earn interest."
        interest = round(self.balance * self.interest_rate, 2)
        if interest <= 0:
            return False, "Interest amount is too small to credit."
        self.balance = round(self.balance + interest, 2)
        self.record_transaction(
            "interest", interest, f"Interest @ {self.interest_rate * 100:.1f}%"
        )
        return True, f"Interest of {interest:,.2f} credited."

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update(
            {
                "interest_rate": self.interest_rate,
                "monthly_withdrawal_limit": self.monthly_withdrawal_limit,
                "monthly_withdrawals": self.monthly_withdrawals,
                "last_withdrawal_month": self.last_withdrawal_month,
            }
        )
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "SavingsAccount":
        return cls(
            account_number=data["account_number"],
            owner=data["owner"],
            pin_hash=data["pin_hash"],
            balance=data.get("balance", 0.0),
            transactions=data.get("transactions", []),
            failed_attempts=data.get("failed_attempts", 0),
            is_blocked=data.get("is_blocked", False),
            daily_withdrawn=data.get("daily_withdrawn", 0.0),
            last_withdrawal_date=data.get("last_withdrawal_date", ""),
            per_tx_limit=data.get("per_tx_limit", 20000.0),
            daily_limit=data.get("daily_limit", 50000.0),
            min_balance=data.get("min_balance", 1000.0),
            interest_rate=data.get("interest_rate", 0.03),
            monthly_withdrawal_limit=data.get("monthly_withdrawal_limit", 4),
            monthly_withdrawals=data.get("monthly_withdrawals", 0),
            last_withdrawal_month=data.get("last_withdrawal_month", ""),
        )


class CurrentAccount(Account):
    """Current account allowing overdrafts up to a configured limit."""

    def __init__(self, *args, overdraft_limit: float = 10000.0, **kwargs) -> None:
        kwargs.setdefault("min_balance", 0.0)
        super().__init__(*args, **kwargs)
        self.overdraft_limit = float(overdraft_limit)

    def account_type(self) -> str:
        return "Current"

    def _minimum_allowed_balance(self) -> float:
        return -self.overdraft_limit

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["overdraft_limit"] = self.overdraft_limit
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "CurrentAccount":
        return cls(
            account_number=data["account_number"],
            owner=data["owner"],
            pin_hash=data["pin_hash"],
            balance=data.get("balance", 0.0),
            transactions=data.get("transactions", []),
            failed_attempts=data.get("failed_attempts", 0),
            is_blocked=data.get("is_blocked", False),
            daily_withdrawn=data.get("daily_withdrawn", 0.0),
            last_withdrawal_date=data.get("last_withdrawal_date", ""),
            per_tx_limit=data.get("per_tx_limit", 20000.0),
            daily_limit=data.get("daily_limit", 50000.0),
            min_balance=data.get("min_balance", 0.0),
            overdraft_limit=data.get("overdraft_limit", 10000.0),
        )


def account_from_dict(data: dict) -> Account:
    """Factory that restores the matching Account subclass from saved JSON data."""
    acc_class = data.get("account_class", "Standard")
    if acc_class == "Savings":
        return SavingsAccount.from_dict(data)
    if acc_class == "Current":
        return CurrentAccount.from_dict(data)
    return Account.from_dict(data)


class NoteDispenser:
    """Manages limited ATM cash note denominations and exact-change dispensing."""

    def __init__(self, notes: dict[int, int] | None = None) -> None:
        source = notes if notes is not None else DEFAULT_NOTES
        self.notes: dict[int, int] = {
            int(denom): int(count)
            for denom, count in sorted(source.items(), key=lambda item: int(item[0]), reverse=True)
        }

    def total_cash(self) -> int:
        """Return total value of cash remaining in the ATM."""
        return sum(denom * count for denom, count in self.notes.items())

    def calculate_notes(self, amount: float) -> dict[int, int] | None:
        """
        Determine exact note counts to dispense `amount`, or return None if impossible.
        Uses bounded search with memoization so non-greedy combinations are found.
        """
        if amount <= 0 or int(amount) != amount:
            return None
        target = int(amount)
        if target > self.total_cash():
            return None

        denoms = sorted(self.notes.keys(), reverse=True)
        failed_states: set[tuple[int, int]] = set()

        def search(idx: int, remaining: int) -> dict[int, int] | None:
            if remaining == 0:
                return {}
            if idx >= len(denoms) or (idx, remaining) in failed_states:
                return None

            denom = denoms[idx]
            max_take = min(self.notes[denom], remaining // denom)
            for count in range(max_take, -1, -1):
                rest = search(idx + 1, remaining - count * denom)
                if rest is not None:
                    if count > 0:
                        return {denom: count, **rest}
                    return rest

            failed_states.add((idx, remaining))
            return None

        return search(0, target)

    def dispense(self, amount: float) -> dict[int, int] | None:
        """Deduct notes for `amount` if exact payout is possible, and return breakdown."""
        plan = self.calculate_notes(amount)
        if plan is None:
            return None
        for denom, count in plan.items():
            self.notes[denom] -= count
        return plan

    def restock(self, denomination: int, count: int) -> tuple[bool, str]:
        """Add notes of an existing denomination to the ATM."""
        if denomination not in self.notes:
            return False, f"Unsupported denomination: {denomination}."
        if count <= 0:
            return False, "Note count must be positive."
        self.notes[denomination] += count
        return True, f"Added {count} x {denomination:,} notes."


def create_default_accounts() -> dict[str, Account]:
    """Preload default accounts (including Ada Obi 1001 / 4321 for quick testing)."""
    return {
        "1001": SavingsAccount(
            account_number="1001",
            owner="Ada Obi",
            pin_hash=hash_pin("4321"),
            balance=50000.0,
        ),
        "1002": CurrentAccount(
            account_number="1002",
            owner="Chidi Eze",
            pin_hash=hash_pin("1234"),
            balance=25000.0,
            overdraft_limit=10000.0,
        ),
        "1003": SavingsAccount(
            account_number="1003",
            owner="Zainab Bello",
            pin_hash=hash_pin("5678"),
            balance=80000.0,
        ),
        "1004": Account(
            account_number="1004",
            owner="Tunde Bakare",
            pin_hash=hash_pin("2468"),
            balance=15000.0,
        ),
    }


def build_receipt_text(
    action: str,
    account: Account,
    amount: float,
    extra_lines: list[str] | None = None,
) -> str:
    """Create a plain-text receipt string suitable for screen display and file saving."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "=" * 42,
        "           PYTHON ATM RECEIPT",
        "=" * 42,
        f"Date/Time:      {now_str}",
        f"Account No:     {account.account_number} ({account.account_type()})",
        f"Account Holder: {account.owner}",
        f"Transaction:    {action}",
        f"Amount:         {amount:,.2f}",
        f"New Balance:    {account.balance:,.2f}",
    ]
    if extra_lines:
        lines.extend(extra_lines)
    lines.append("=" * 42)
    return "\n".join(lines) + "\n"


class ATM:
    """Coordinates customer sessions, ATM cash notes, persistence, and admin operations."""

    MAX_PIN_ATTEMPTS = 3

    def __init__(
        self,
        data_file: str = "data/atm_data.json",
        receipt_dir: str = "receipts",
    ) -> None:
        self.data_file = data_file
        self.receipt_dir = receipt_dir
        self.current_account: Account | None = None
        self.startup_message: str | None = None

        data, status_msg = load_data(self.data_file)
        if data is None:
            self.startup_message = status_msg
            self.accounts = create_default_accounts()
            self.dispenser = NoteDispenser()
            self.admin_pin_hash = hash_pin(DEFAULT_ADMIN_PIN)
            self.save()
        else:
            self.admin_pin_hash = data.get("admin_pin_hash", hash_pin(DEFAULT_ADMIN_PIN))
            raw_notes = data.get("notes", DEFAULT_NOTES)
            self.dispenser = NoteDispenser({int(k): int(v) for k, v in raw_notes.items()})
            self.accounts = {
                acc_num: account_from_dict(acc_data)
                for acc_num, acc_data in data["accounts"].items()
            }

    def save(self) -> None:
        """Persist current ATM state to JSON."""
        save_data(self.data_file, self.accounts, self.dispenser.notes, self.admin_pin_hash)

    def login(self, account_number: str, pin: str) -> tuple[bool, str]:
        """Authenticate a customer, blocking the account after 3 wrong PIN attempts."""
        acc_num = account_number.strip()
        account = self.accounts.get(acc_num)
        if account is None:
            return False, "Account number not found."
        if account.is_blocked:
            return False, "This account is blocked. Please contact an admin to unblock it."

        if account.verify_pin(pin):
            account.failed_attempts = 0
            self.current_account = account
            self.save()
            return True, f"Welcome, {account.owner}."

        account.failed_attempts += 1
        remaining = self.MAX_PIN_ATTEMPTS - account.failed_attempts
        if remaining <= 0:
            account.is_blocked = True
            self.save()
            return (
                False,
                "Incorrect PIN. Account has been blocked after 3 failed attempts.",
            )

        self.save()
        return False, f"Incorrect PIN. {remaining} attempt(s) remaining."

    def logout(self) -> str:
        """End the current customer session."""
        if self.current_account is None:
            return "No customer is currently logged in."
        name = self.current_account.owner
        self.current_account = None
        return f"Goodbye, {name}. You have been logged out."

    def check_balance(self) -> float:
        """Return the logged-in customer's balance."""
        if self.current_account is None:
            raise RuntimeError("No customer is logged in.")
        return self.current_account.check_balance()

    def deposit(self, amount: float) -> tuple[bool, str, dict | None]:
        """Deposit money into the logged-in account and save a receipt."""
        if self.current_account is None:
            return False, "No customer is logged in.", None

        ok, msg = self.current_account.deposit(amount)
        if not ok:
            return False, msg, None

        self.save()
        receipt_text = build_receipt_text("Deposit", self.current_account, amount)
        receipt_path = save_receipt(
            receipt_text, self.current_account.account_number, self.receipt_dir
        )
        return True, msg, {
            "amount": amount,
            "balance": self.current_account.balance,
            "receipt_text": receipt_text,
            "receipt_path": receipt_path,
        }

    def withdraw(
        self, amount: float, today_str: str | None = None
    ) -> tuple[bool, str, dict | None]:
        """Withdraw cash if account rules and ATM note inventory allow exact payout."""
        if self.current_account is None:
            return False, "No customer is logged in.", None

        ok, msg = self.current_account.can_withdraw(amount, today_str=today_str)
        if not ok:
            return False, msg, None

        note_plan = self.dispenser.calculate_notes(amount)
        if note_plan is None:
            return (
                False,
                "ATM cannot dispense the exact amount with available notes. "
                f"Available denominations: {sorted(self.dispenser.notes.keys())}.",
                None,
            )

        self.dispenser.dispense(amount)
        ok, msg = self.current_account.withdraw(amount, today_str=today_str)
        if not ok:
            return False, msg, None

        self.save()
        notes_summary = ", ".join(
            f"{count} x {denom:,}" for denom, count in sorted(note_plan.items(), reverse=True)
        )
        receipt_text = build_receipt_text(
            "Withdrawal",
            self.current_account,
            amount,
            extra_lines=[f"Notes dispensed: {notes_summary}"],
        )
        receipt_path = save_receipt(
            receipt_text, self.current_account.account_number, self.receipt_dir
        )
        return True, msg, {
            "amount": amount,
            "balance": self.current_account.balance,
            "notes": note_plan,
            "notes_summary": notes_summary,
            "receipt_text": receipt_text,
            "receipt_path": receipt_path,
        }

    def transfer(self, to_account_number: str, amount: float) -> tuple[bool, str, dict | None]:
        """Transfer money from the logged-in account to another existing account."""
        if self.current_account is None:
            return False, "No customer is logged in.", None

        target = self.accounts.get(to_account_number.strip())
        ok, msg = self.current_account.transfer(target, amount)
        if not ok:
            return False, msg, None

        self.save()
        receipt_text = build_receipt_text(
            "Transfer",
            self.current_account,
            amount,
            extra_lines=[f"Recipient:      {target.account_number} ({target.owner})"],
        )
        receipt_path = save_receipt(
            receipt_text, self.current_account.account_number, self.receipt_dir
        )
        return True, msg, {
            "amount": amount,
            "balance": self.current_account.balance,
            "recipient": target.account_number,
            "recipient_name": target.owner,
            "receipt_text": receipt_text,
            "receipt_path": receipt_path,
        }

    def change_pin(self, old_pin: str, new_pin: str) -> tuple[bool, str]:
        """Change the logged-in customer's PIN."""
        if self.current_account is None:
            return False, "No customer is logged in."
        ok, msg = self.current_account.change_pin(old_pin, new_pin)
        if ok:
            self.save()
        return ok, msg

    def apply_interest_current(self) -> tuple[bool, str, dict | None]:
        """Apply interest if the logged-in account is a SavingsAccount."""
        if self.current_account is None:
            return False, "No customer is logged in.", None
        if not isinstance(self.current_account, SavingsAccount):
            return False, "Interest is only available for Savings accounts.", None

        before = self.current_account.balance
        ok, msg = self.current_account.apply_interest()
        if not ok:
            return False, msg, None

        earned = round(self.current_account.balance - before, 2)
        self.save()
        receipt_text = build_receipt_text("Interest Credit", self.current_account, earned)
        receipt_path = save_receipt(
            receipt_text, self.current_account.account_number, self.receipt_dir
        )
        return True, msg, {
            "amount": earned,
            "balance": self.current_account.balance,
            "receipt_path": receipt_path,
        }

    # ---- Admin methods ----

    def verify_admin_pin(self, pin: str) -> bool:
        """Verify the admin PIN against the stored hash."""
        return hash_pin(pin) == self.admin_pin_hash

    def admin_create_account(
        self,
        account_number: str,
        owner: str,
        pin: str,
        initial_balance: float,
        account_type: str = "Savings",
    ) -> tuple[bool, str]:
        """Create a new Standard, Savings, or Current account."""
        acc_num = account_number.strip()
        if not acc_num:
            return False, "Account number cannot be empty."
        if acc_num in self.accounts:
            return False, f"Account {acc_num} already exists."
        owner = owner.strip()
        if not owner:
            return False, "Owner name cannot be empty."
        pin = pin.strip()
        if not (pin.isdigit() and len(pin) == 4):
            return False, "PIN must be exactly 4 digits."
        if initial_balance < 0:
            return False, "Initial balance cannot be negative."

        kind = account_type.strip().lower()
        if kind == "savings":
            new_acc: Account = SavingsAccount(
                acc_num, owner, hash_pin(pin), balance=initial_balance
            )
        elif kind == "current":
            new_acc = CurrentAccount(
                acc_num, owner, hash_pin(pin), balance=initial_balance
            )
        else:
            new_acc = Account(acc_num, owner, hash_pin(pin), balance=initial_balance)

        self.accounts[acc_num] = new_acc
        self.save()
        return True, f"{new_acc.account_type()} account {acc_num} created for {owner}."

    def admin_unblock_account(self, account_number: str) -> tuple[bool, str]:
        """Unblock a locked customer account and reset failed attempts."""
        acc = self.accounts.get(account_number.strip())
        if acc is None:
            return False, "Account not found."
        if not acc.is_blocked:
            return False, "Account is not blocked."
        acc.is_blocked = False
        acc.failed_attempts = 0
        self.save()
        return True, f"Account {acc.account_number} ({acc.owner}) has been unblocked."

    def get_statistics(self) -> dict:
        """Return transaction statistics across all accounts."""
        return compute_statistics(self.accounts)
