# rhinventory
RH inventory 

## Jak se Alembic?

```
    # Řeknu si Sankymu aby mi vysvětlil alembic.ini...

    # Jako git status
    alembic current

    # Udělal jsem novou tabulku, chci aby jí alembic přemigroval
    alembic revision --autogenerate -m "Add File table"

    # omrknu alembic/versions/3822d04489a0_add_file_table.py, jestli tam je to co chci...

    # Spustím migraci
    alembic upgrade head
```