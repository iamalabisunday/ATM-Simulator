"""
ui.py — Member B (Display & Input)
Handles menus, formatted screens, input validation, mini-statements,
admin screens, and receipt printing.
"""

from models import ATM, SavingsAccount


def prompt_amount(label: str = "Amount: ") -> float | None:
    """Read a numeric amount from input, returning None if invalid."""
    raw = input(label).strip().replace(",", "")
    try:
        return float(raw)
    except ValueError:
        print("Invalid amount. Please enter a valid number.")
        return None


def prompt_int(label: str) -> int | None:
    """Read an integer from input, returning None if invalid."""
    raw = input(label).strip()
    try:
        return int(raw)
    except ValueError:
        print("Invalid number. Please enter a whole number.")
        return None


def print_mini_statement(account) -> None:
    """Display the last 5 transactions for an account."""
    entries = account.mini_statement(5)
    print("\n--- Mini-Statement (Last 5 Transactions) ---")
    if not entries:
        print("No transactions recorded yet.")
        return

    print(f"{'Date/Time':<20} {'Type':<14} {'Amount':>12} {'Balance':>12}  Details")
    print("-" * 76)
    for tx in entries:
        print(
            f"{tx['timestamp']:<20} "
            f"{tx['type']:<14} "
            f"{tx['amount']:>12,.2f} "
            f"{tx['balance_after']:>12,.2f}  "
            f"{tx.get('details', '')}"
        )


def print_all_accounts(atm: ATM) -> None:
    """Display a formatted table of all accounts in the ATM."""
    print("\n--- All Registered Accounts ---")
    print(f"{'Acc No':<8} {'Owner':<18} {'Type':<10} {'Balance':>14} {'Status':<10}")
    print("-" * 66)
    for acc in atm.accounts.values():
        status = "BLOCKED" if acc.is_blocked else "Active"
        print(
            f"{acc.account_number:<8} "
            f"{acc.owner:<18} "
            f"{acc.account_type():<10} "
            f"{acc.balance:>14,.2f} "
            f"{status:<10}"
        )


def print_atm_cash(atm: ATM) -> None:
    """Display total cash left in the ATM and breakdown by note denomination."""
    print("\n--- ATM Cash Inventory ---")
    for denom, count in sorted(atm.dispenser.notes.items(), reverse=True):
        print(f"  {denom:>6,} note : {count:>4} notes  (Subtotal: {denom * count:>10,})")
    print("-" * 42)
    print(f"  Total Cash Left: {atm.dispenser.total_cash():,.2f}")


def print_statistics(atm: ATM) -> None:
    """Display ATM transaction statistics."""
    stats = atm.get_statistics()
    print("\n--- ATM Statistics ---")
    print(f"Total transactions: {stats['total_transactions']}")

    counts = stats["counts_by_type"]
    if counts:
        print("Transactions per type:")
        for tx_type, count in sorted(counts.items()):
            print(f"  - {tx_type:<14}: {count}")
    else:
        print("Transactions per type: None yet.")

    if stats["largest_deposit"]:
        amt, acc, ts = stats["largest_deposit"]
        print(f"Largest deposit:    {amt:,.2f} (Account {acc} at {ts})")
    else:
        print("Largest deposit:    None")

    if stats["largest_withdrawal"]:
        amt, acc, ts = stats["largest_withdrawal"]
        print(f"Largest withdrawal: {amt:,.2f} (Account {acc} at {ts})")
    else:
        print("Largest withdrawal: None")

    if stats["busiest_hour"]:
        hour, count = stats["busiest_hour"]
        print(f"Busiest hour:       {hour:02d}:00 - {hour:02d}:59 ({count} transaction(s))")
    else:
        print("Busiest hour:       N/A")


def handle_customer_session(atm: ATM) -> None:
    """Run the logged-in customer menu loop until logout."""
    while atm.current_account is not None:
        acc = atm.current_account
        print(f"\n--- Customer Menu ({acc.owner} | {acc.account_type()}) ---")
        print("1. Check Balance")
        print("2. Deposit")
        print("3. Withdraw")
        print("4. Transfer")
        print("5. Mini-Statement (Last 5)")
        print("6. Change PIN")
        print("7. Apply Interest (Savings only)")
        print("8. Logout")

        choice = input("Menu choice: ").strip()

        if choice == "1":
            balance = atm.check_balance()
            print(f"\nCurrent balance: {balance:,.2f}")

        elif choice == "2":
            amount = prompt_amount("Amount to deposit: ")
            if amount is None:
                continue
            ok, msg, info = atm.deposit(amount)
            print(f"\n{msg}")
            if ok and info:
                print(f"Amount deposited: {info['amount']:,.2f}")
                print(f"New balance:      {info['balance']:,.2f}")
                print(f"Receipt saved:    {info['receipt_path']}")

        elif choice == "3":
            amount = prompt_amount("Amount: ")
            if amount is None:
                continue
            ok, msg, info = atm.withdraw(amount)
            print(f"\n{msg}")
            if ok and info:
                print(f"Amount withdrawn: {info['amount']:,.2f}")
                print(f"New balance:      {info['balance']:,.2f}")
                print(f"Notes dispensed:  {info['notes_summary']}")
                print(f"Receipt saved:    {info['receipt_path']}")

        elif choice == "4":
            target_acc = input("Recipient account number: ").strip()
            amount = prompt_amount("Amount to transfer: ")
            if amount is None:
                continue
            ok, msg, info = atm.transfer(target_acc, amount)
            print(f"\n{msg}")
            if ok and info:
                print(f"Amount transferred: {info['amount']:,.2f}")
                print(f"New balance:        {info['balance']:,.2f}")
                print(f"Receipt saved:      {info['receipt_path']}")

        elif choice == "5":
            print_mini_statement(acc)

        elif choice == "6":
            old_pin = input("Enter current PIN: ").strip()
            new_pin = input("Enter new 4-digit PIN: ").strip()
            ok, msg = atm.change_pin(old_pin, new_pin)
            print(f"\n{msg}")

        elif choice == "7":
            if not isinstance(acc, SavingsAccount):
                print("\nInterest is only available for Savings accounts.")
                continue
            ok, msg, info = atm.apply_interest_current()
            print(f"\n{msg}")
            if ok and info:
                print(f"New balance:   {info['balance']:,.2f}")
                print(f"Receipt saved: {info['receipt_path']}")

        elif choice == "8":
            print(f"\n{atm.logout()}")

        else:
            print("\nInvalid choice. Please select 1 to 8.")


def handle_admin_session(atm: ATM) -> None:
    """Authenticate and run the admin menu loop."""
    pin = input("Enter Admin PIN: ").strip()
    if not atm.verify_admin_pin(pin):
        print("\nIncorrect Admin PIN. Access denied.")
        return

    print("\nAdmin login successful.")
    while True:
        print("\n--- Admin Menu ---")
        print("1. View All Accounts")
        print("2. Create New Account")
        print("3. Unblock Account")
        print("4. View ATM Cash Left")
        print("5. Restock ATM Notes")
        print("6. View Statistics")
        print("7. Exit Admin Mode")

        choice = input("Admin choice: ").strip()

        if choice == "1":
            print_all_accounts(atm)

        elif choice == "2":
            acc_num = input("New account number: ").strip()
            owner = input("Owner full name: ").strip()
            acc_pin = input("Set 4-digit PIN: ").strip()
            acc_type = input("Account type (Savings / Current / Standard): ").strip() or "Savings"
            bal = prompt_amount("Initial deposit amount: ")
            if bal is None:
                continue
            ok, msg = atm.admin_create_account(acc_num, owner, acc_pin, bal, acc_type)
            print(f"\n{msg}")

        elif choice == "3":
            acc_num = input("Account number to unblock: ").strip()
            ok, msg = atm.admin_unblock_account(acc_num)
            print(f"\n{msg}")

        elif choice == "4":
            print_atm_cash(atm)

        elif choice == "5":
            denom = prompt_int("Note denomination (e.g. 1000, 500, 200, 100): ")
            if denom is None:
                continue
            count = prompt_int("Number of notes to add: ")
            if count is None:
                continue
            ok, msg = atm.dispenser.restock(denom, count)
            if ok:
                atm.save()
            print(f"\n{msg}")

        elif choice == "6":
            print_statistics(atm)

        elif choice == "7":
            print("\nExiting Admin Mode.")
            break

        else:
            print("\nInvalid choice. Please select 1 to 7.")


def run_atm(atm: ATM) -> None:
    """Run the main ATM CLI loop."""
    print("========================================")
    print("       WELCOME TO PYTHON ATM")
    print("========================================")
    if atm.startup_message:
        print(f"[Notice] {atm.startup_message}")

    while True:
        print("\n--- Main Menu ---")
        print("1. Customer Login")
        print("2. Admin Mode")
        print("3. Exit")

        try:
            choice = input("Select an option: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nThank you for using Python ATM. Goodbye!")
            break

        if choice == "1":
            try:
                acc_num = input("Account number: ").strip()
                pin = input("PIN: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nLogin cancelled.")
                continue

            ok, msg = atm.login(acc_num, pin)
            print(f"\n{msg}")
            if ok:
                try:
                    handle_customer_session(atm)
                except (EOFError, KeyboardInterrupt):
                    print(f"\n{atm.logout()}")

        elif choice == "2":
            try:
                handle_admin_session(atm)
            except (EOFError, KeyboardInterrupt):
                print("\nExited Admin Mode.")

        elif choice == "3":
            print("\nThank you for using Python ATM. Goodbye!")
            break

        else:
            print("\nInvalid option. Please choose 1, 2, or 3.")
