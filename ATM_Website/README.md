# ATM Simulator — Web Edition (`ATM_Website`)

Interactive browser version of **Project 10 — ATM Simulator** powered by Python's built-in `http.server` and the core OOP modules (`models.py` and `storage.py`) with **zero external dependencies**.

## How to Run

```bash
cd "ATM_Website"
python3 server.py
```

Then open **http://127.0.0.1:8000** in your browser.

## Features

- **Customer ATM Kiosk**: On-screen keypad, quick-fill demo account pills, live balance & limits bar, quick-cash withdrawal buttons, deposit, transfer, 5-item mini-statement, PIN change, and Savings interest credit.
- **Cash Dispenser & Printable Receipt Slip**: Visual breakdown of exact notes dispensed plus a live printable ATM slip (`Print / Save PDF`).
- **Admin Console** (PIN `0000`): View all accounts, unblock locked accounts, create new accounts, restock ATM notes, and view live statistics.
