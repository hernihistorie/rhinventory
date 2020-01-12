from sys import argv
import csv
from datetime import datetime
from decimal import Decimal
from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.db import Asset, AssetStatus, Category
import json
from pprint import pprint


csv_file = {
    'game':'/mnt/z/GM.csv',
    'console':'/mnt/z/GC.csv',
    'console accesory':'/mnt/z/PP.csv',
    'other software':'/mnt/z/SW.csv',
    'keyboard':'/mnt/z/Kláv.csv',
    'computer mouse':'/mnt/z/Myš.csv',
    'television':'/mnt/z/TV.csv',
    'monitor':'/mnt/z/M.csv',

}

asset_titles={
    "keyboard": "klávesnice",
    "computer mouse": "Myš",
    "television": "Televizor",
    "monitor": "Monitor",                    
    }

def row_is_valid(row):
    if "Název" in row.keys():
        if row["Název"].strip() != '' and row["Název"].strip() != '-' and ('reserved' not in row["Název"].strip().lower()):
            return True
        else: return False
    elif "Typ" in row.keys():
        if row["Typ"].strip() != '': return True
        else: return False
    elif "Výrobce" in row.keys():
        if row["Výrobce"].strip() != '': return True
        else: return False
    else: return False

app=create_app()
with app.app_context(): 
    for key in csv_file:
        with open (csv_file[key], newline='') as f:
            reader = csv.reader(f)
            cat=Category.query.filter(Category.name==key).one()
            pprint ([key, csv_file[key], cat.prefix])
            header = next(reader)

             

            for row in reader:
                row = dict(zip(header, row))
                if row_is_valid(row):
                    #pprint(row)
                    title=row.get("Název", asset_titles.get(key,"")).strip()
                    
                    pprint ([row["Inv. č."], title])
                    asset = Asset(
                        category=cat,
                        name= title,
                        manufacturer=row["Výrobce"].strip(),
                        note=row.get("Poznámka","").strip(),
                        custom_code=int(row["Inv. č."].strip().replace(cat.prefix,"")),
                        condition=0,
                        functionality=0,
                        status=AssetStatus.unknown
                    )
                    #pprint(asset)
                    db.session.add(asset)

            db.session.commit()

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



