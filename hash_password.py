#!/usr/bin/env python3
"""Generate a bcrypt password hash for Streamlit secrets.

Usage:
    python3 hash_password.py
    python3 hash_password.py 'YourPasswordHere'
"""

from __future__ import annotations

import getpass
import sys

import bcrypt


def main() -> None:
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    if len(password) < 8:
        print("Warning: password is shorter than 8 characters.", file=sys.stderr)

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    print()
    print("Put this in Streamlit Secrets under [auth.credentials]:")
    print()
    print(f'  "email@example.com" = "{hashed.decode()}"')
    print()


if __name__ == "__main__":
    main()
