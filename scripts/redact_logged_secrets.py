"""Redact secrets written to the logs table before log.py redacted them.

Dry run by default:

    uv run python scripts/redact_logged_secrets.py
    uv run python scripts/redact_logged_secrets.py --apply
"""
import argparse

from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.models.log import redact_logged_secrets

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--apply", action="store_true", help="write the changes instead of only counting them")
args = parser.parse_args()

app = create_app()
with app.app_context():
    changed = redact_logged_secrets(db.session)
    if args.apply:
        db.session.commit()
        print(f"Redacted {changed} log items.")
    else:
        db.session.rollback()
        print(f"Would redact {changed} log items. Run with --apply to write the changes.")
