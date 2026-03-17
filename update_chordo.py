#!/usr/bin/env python3
# Chordo GitHub: https://github.com/ylub/chordo

import shlex
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog


def run(cmd):
    print("+", " ".join(shlex.quote(part) for part in cmd))
    subprocess.run(cmd, check=True)


def main():
    if len(sys.argv) >= 2:
        message = " ".join(sys.argv[1:]).strip()
    else:
        root = tk.Tk()
        root.withdraw()
        message = simpledialog.askstring(
            "Chordo Update",
            "Enter commit message:",
            parent=root,
        )
        if message is None:
            return 1
        message = message.strip()

    if not message:
        print("Commit message cannot be empty.")
        try:
            messagebox.showerror("Chordo Update", "Commit message cannot be empty.")
        except Exception:
            pass
        return 1

    try:
        run(["git", "status", "--short"])
        run(["git", "add", "-A"])
        run(["git", "commit", "-m", message])
        run(["git", "push", "origin", "main"])
    except subprocess.CalledProcessError as exc:
        print(f"Command failed with exit code {exc.returncode}.")
        try:
            messagebox.showerror(
                "Chordo Update",
                f"Command failed with exit code {exc.returncode}.",
            )
        except Exception:
            pass
        return exc.returncode

    print("GitHub update complete.")
    try:
        messagebox.showinfo("Chordo Update", "GitHub update complete.")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
