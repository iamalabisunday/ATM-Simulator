# Beginner Python ATM Guide

This project now has a separate beginner-friendly file:

```text
ATM_Simulator_Beginner.py
```

It combines the main Python ideas from `main.py`, `models.py`, `storage.py`, and `ui.py` into one file. The original project files are unchanged.

## Run it

```bash
cd /home/gamp/ATM-Simulator
python3 ATM_Simulator_Beginner.py
```

Demo accounts:

| Account | PIN  | Type     |
| ------- | ---- | -------- |
| 1001    | 4321 | Savings  |
| 1002    | 1234 | Current  |
| 1003    | 5678 | Savings  |
| 1004    | 2468 | Standard |

Admin PIN: `0000`

## Read the file from top to bottom

The file is divided into six commented sections:

1. **Storage functions** — hash PINs, load JSON, save JSON and create receipts.
2. **Account classes** — account rules and account types.
3. **Note dispenser** — find and restock ATM cash notes.
4. **ATM controller** — login and coordinate customer/admin operations.
5. **Menus** — get keyboard input and show results.
6. **Main program** — starts the application.

## Main idea

```text
Main menu
   ↓
ATM controller
   ↓
Account / NoteDispenser
   ↓
Save to JSON and create receipt
```

The menu code should ask for information. The account and ATM classes should make decisions and change data.

## What an object is

An account is represented by an object:

```python
account = SavingsAccount("1001", "Ada Obi", "4321", 50000)
```

The object stores data such as:

- `account.owner`
- `account.balance`
- `account.pin_hash`
- `account.transactions`

It also provides methods:

- `account.deposit(...)`
- `account.withdraw(...)`
- `account.transfer(...)`
- `account.change_pin(...)`

## What inheritance means

```text
Account
  ├── SavingsAccount
  └── CurrentAccount
```

`SavingsAccount` and `CurrentAccount` start with everything from `Account`. Each subclass adds or changes only its special rules.

- Savings accounts earn 3% interest.
- Savings accounts allow only four withdrawals per month.
- Current accounts allow a negative balance to -10,000.
- Standard accounts keep at least 1,000 in the account.

## Normal withdrawal flow

```text
User enters 5000
    ↓
ATM.withdraw(5000)
    ↓
Account.can_withdraw(5000)
    ↓
NoteDispenser.find_notes(5000)
    ↓
Account.withdraw(5000)
    ↓
Subtract the notes
    ↓
Save data and create receipt
```

Every step must return success before the final state changes.

## JSON persistence

When the program starts, it tries to load `beginner_data.json`.

Saved data includes:

- account names and balances
- PIN hashes
- blocked status
- transactions
- ATM notes
- admin PIN hash

PINs are stored as hashes, not plain text.

## Receipt files

Each successful deposit, withdrawal, transfer or interest action creates a file in:

```text
beginner_receipts/
```

## Beginner reading order

1. `format_money()`
2. `hash_pin()`
3. `Account.__init__()`
4. `Account.deposit()`
5. `Account.can_withdraw()`
6. `Account.withdraw()`
7. `SavingsAccount` and `CurrentAccount`
8. `NoteDispenser.find_notes()`
9. `ATM.login()`
10. `ATM.withdraw()`
11. `customer_menu()`
12. `main()`

## Important method pattern

Many methods return two values:

```python
allowed, message = account.deposit(amount)
```

`allowed` says whether the operation worked. `message` explains why.

Some ATM methods return three values:

```python
allowed, message, info = atm.withdraw(amount)
```

`info` contains extra receipt or note information for a successful operation.
