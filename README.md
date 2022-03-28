# rhinventory
RH inventory 

## Jak se Alembic?

```
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

## How to run scripts

`PYTHONPATH=. python scripts/script.py`