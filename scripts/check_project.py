"""Run the supported project checks from any working directory."""

from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
for args in [
    ("check",),
    ("makemigrations", "--check", "--dry-run"),
    ("migrate", "--check"),
    ("test", "--verbosity", "2"),
]:
    print("\nRunning: manage.py " + " ".join(args), flush=True)
    subprocess.run([sys.executable, "manage.py", *args], cwd=root, check=True)
