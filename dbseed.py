# from sys import argv
import csv
from datetime import datetime
from decimal import Decimal
from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.db import Asset, AssetStatus, Category, AssetMeta, Transaction, TransactionType, log
# import json
from pprint import pprint


csv_file = {
    'game': './docs/GM.csv',
    'console': './docs/GC.csv',
    'console accesory': './docs/PP.csv',
    'other software': './docs/SW.csv',
    'keyboard': './docs/Kláv.csv',
    'computer mouse': './docs/Myš.csv',
    'television': './docs/TV.csv',
    'monitor': './docs/M.csv',

}


user_map = {
    "Morx": 2,
    "BlackChar": 4,
    "Blackie": 4,
    "BC?": 4,
    "Sanky": 5,
    "Scyther": 6,
    "scyther": 6,
    "Scyther?": 6,
    "Sczther": 6,
    "Behold3r": 7,
    "John Beak": 9,
    "Terrion": 10,
    "Arlette": 11,
    "Zdeněk": 103,
    "fiflik": 28,
    "František": 22,
    "Brambora": 56,
    "Buizel": 2,                     # vse od Buizela stejne domlouval morx
    '“Někdo to poslal Morxovi”': 2,  # wat
    "Retroherna": 6,                 # Scyther je RetroHerna
    "John Bleak Char": 4,            # facepalm



}

asset_titles = {
    "keyboard": "klávesnice",
    "computer mouse": "Myš",
    "television": "Televizor",
    "monitor": "Monitor",
}


game_meta = {
    "Platform": "Platforma",
    "Medium": "Formát",
    "Product No": "Písmena a čísla",
}

console_meta = {
}

mouse_meta = {
    "Color": "Vzhled",
    "Connection": "Typ",
    "Type": "Styl",

}

keyboard_meta = {
    "Color": "Vzhled",
    "Connection": "Typ",
}

television_meta = {
    "Size": "Úhlopříčka",

}

monitor_meta = {
    "Size": "Úhlopříčka",
}


def row_is_valid(row):
    if "Název" in row.keys():
        if row["Název"].strip() != '' and row["Název"].strip() != '-' and ('reserved' not in row["Název"].strip().lower()):
            return True
        else:
            return False
    elif "Typ" in row.keys():
        if row["Typ"].strip() != '':
            return True
        else:
            return False
    elif "Výrobce" in row.keys():
        if row["Výrobce"].strip() != '':
            return True
        else:
            return False
    else:
        return False


def coerce_int(value):  # F&&KIN PYTHON TO NEUMI NAPSAT NA JEDEN RADEK
    try:
        return int(value)
    except Exception:
        return None


def value_or_none(value):
    return value if value else None


app = create_app()
with app.app_context():
    #    db.create_all()

    for key in csv_file:
        with open(csv_file[key], newline='') as f:
            reader = csv.reader(f)
            cat = Category.query.filter(Category.name == key).one()
            pprint([key, csv_file[key], cat.prefix])
            header = next(reader)

            for row in reader:
                row = dict(zip(header, row))
                if row_is_valid(row):
                    # pprint(row)
                    title = row.get("Název", asset_titles.get(key, "")).strip()

                    print(row["Inv. č."].strip() + "\t- " + title + " :\t\t", end='')
                    asset = Asset(
                        category=cat,
                        name=title,
                        manufacturer=value_or_none(row["Výrobce"].strip()),
                        note=row.get("Poznámka", "").strip(),
                        model=value_or_none(row.get("Model", "").strip()),
                        serial=value_or_none(
                            row.get("Sériové číslo", "").strip()),
                        custom_code=int(
                            row["Inv. č."].strip().replace(cat.prefix, "")),
                        num_photos=0,
                        condition=0,
                        functionality=0,
                        status=AssetStatus.unknown
                    )
                    print(" AS", end='')
                    # pprint(asset)
                    tx = Transaction(
                        transaction_type=TransactionType.acquisition,
                        user_id=user_map.get(
                            row.get("Pořízeno kým", "").strip()),
                        counterparty=row.get("Pořízeno od", "").strip(),
                        cost=coerce_int(row.get("Pořízeno za", "")) or None,
                        date=None,
                        note="Import z Googlu:\nPořídil(a): " + row.get("Pořízeno kým", "").strip() + "\n za: " + row.get(
                            "Pořízeno za", "").strip() + "\n od: " + row.get("Pořízeno od", "").strip()
                    )
                    asset.transactions.append(tx)
                    print(" TX", end='')

                    # if cat.name == "console":

                    db.session.add(asset)
                    db.session.commit()
                    print(" SAVE", end='')
                    log("Create", asset)
                    #pprint(tx)
                    log("Create", tx)

                    # TODO: log neuklada MN vazbu
                    print(" LOG.")


    # def get_category(code):
        # if code in db_categories:
        #     return db_categories[code]
        # else:
        #     category = Category.query.filter(Category.code == str(code)).scalar()
        #     if not category:
        #         category = Category(code=code, name=code, identifier=code, tally=True, deleted=False)
        #         category.save()
        #         log("Create", category)
        #     db_categories[code] = category
        #     return category
