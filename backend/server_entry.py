"""PyInstaller uchun kirish nuqtasi:  pyinstaller --name engcheck-server --onedir server_entry.py"""
import sys

from engcheck.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
