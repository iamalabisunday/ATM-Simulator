"""
main.py — Entry point for Project 10: ATM Simulator (Group 7)
"""

from models import ATM
from ui import run_atm


def main() -> None:
    atm = ATM(data_file="data/atm_data.json", receipt_dir="receipts")
    run_atm(atm)


if __name__ == "__main__":
    main()
