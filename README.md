# rhinventory
Kód pro inventář spolku Herní historie.

## Nasazení
Dependencies:

- PostgreSQL database
- Copy `.env_example` to `.env` and fill in variables
- Copy `alembic.ini_example` to `alembic.ini` and fill in PostgreSQL database URL
- Run:
```bash
    poetry init
    poetry run python dbseed.py
    alembic heads
    alembic stamp <revision>
```

Where `<revision>` is the latest Alembic revision shown from `alembic heads`.

The first registered user should be given admin permissions.

Run with `poetry run flask run`.

## Jak se Alembic?

```bash
    # Řeknu si Sankymu aby mi vysvětlil alembic.ini...

    source .venv/bin/activate

    # Jako git status
    alembic current

    # Udělal jsem novou tabulku, chci aby jí alembic přemigroval
    alembic revision --autogenerate -m "Add File table"

    # omrknu alembic/versions/[nová revize].py, jestli tam je to co chci...

    # Spustím migraci
    alembic upgrade head
```

## How to deploy

If there are no database migrations: run the script `./ops/deploy.sh`

If there are database migrations:

```sh
ssh retroherna.org
cd /var/www/rhinventory
sudo -u flask  git pull
sudo -u flask  poetry run  alembic upgrade head
# Correct any issues should they arise
sudo systemctl restart www_rhinventory
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