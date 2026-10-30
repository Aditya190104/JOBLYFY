"""Create a local environment once, without printing or overwriting secrets."""

from pathlib import Path
import secrets

root = Path(__file__).resolve().parent.parent
path = root / ".env"
if path.exists():
    print(".env already exists; no changes made.")
else:
    text = (root / ".env.example").read_text(encoding="utf-8")
    text = text.replace(
        "DJANGO_SECRET_KEY=", "DJANGO_SECRET_KEY=" + secrets.token_urlsafe(64), 1
    )
    with path.open("x", encoding="utf-8") as f:
        f.write(text)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    print("Created private .env for local development.")
