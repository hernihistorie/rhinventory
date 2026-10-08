# rhinventory
Kód pro inventář spolku Herní historie.

## Nasazení
Dependencies:

- PostgreSQL database
- Copy `.env_example` to `.env` and fill in variables
- Copy `alembic.ini_example` to `alembic.ini` and fill in PostgreSQL database URL
- Run:
```bash
    uv sync
    uv run python dbseed.py
    uv run alembic heads
    uv run alembic stamp <revision>
```

Where `<revision>` is the latest Alembic revision shown from `alembic heads`.

The first registered user should be given admin permissions.

Run with `uv run flask run`.

## Run rhinventory
```bash
uv run flask run --debug
```

## Run rhinventory-api
```bash
uv run fastapi dev rhinventory/api/app.py
```

## Jak se Alembic?

```bash
    poetry shell

    # Jako git status
    alembic current

    # Udělal jsem novou tabulku, chci aby jí alembic přemigroval
    alembic revision --autogenerate -m "Add File table"

    # omrknu alembic/versions/[nová revize].py, jestli tam je to co chci...

    # Spustím migraci
    alembic upgrade head
```

## Bumping hhfloppy versions
Have you updated events in hhfloppy?  Run this to update the dependency:

```bash
uv lock --upgrade-package hhfloppy && uv sync
```

## How to deploy

If there are no database migrations: run the script `./ops/deploy.sh`

If there are database migrations: run the script `./ops/deploy_with_migration.sh`

## Embedding

herniarchiv.cz (haweb) shows public rhinventory pages under `/inventory/`, by loading them in an iframe through its own proxy.  The proxy sends these request headers:

- `X-Forwarded-Prefix: /inventory/_frame` – path the proxy serves rhinventory at.  All URLs must therefore be built with `url_for` (or the `site_url` filter for root-relative URLs from elsewhere, such as the database).
- `X-Haweb-Embed: 1` – embed mode: no header, staff-only tools hidden, `noindex, indexifembedded`, and `static/embed.css` and `static/embed.js` are loaded (see `admin/master.html`).
- `X-Haweb-Theme: light|dark` – the visitor's theme on.  Without it, the system preference applies.

To try it locally:

```bash
curl -H 'X-Forwarded-Prefix: /inventory/_frame' -H 'X-Haweb-Embed: 1' http://127.0.0.1:5000/asset/
```

## How to run scripts

`PYTHONPATH=. python scripts/script.py`

## Debugging crashes on prod

Try to check logs with `sudo journalctl -u www_rhinventory -e`.  If that's not enough, run manually with:

```sh
sudo systemctl stop rhinventory
cd /var/www/rhinventory
sudo -u flask ./deploy.sh
```

Once solved:

```sh
sudo systemctl start rhinventory
```

## Upgrading hhfloppy
```sh
uv lock --upgrade-package hhfloppy && uv sync
```

Then update the `SUPPORTED_EVENT_VERSION` in `event_store.py`.
