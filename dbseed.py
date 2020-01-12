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
    'computer':'/mnt/z/PC.csv',
    'console':'/mnt/z/GC.csv'
}

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
                if row["Název"].strip() != '' and row["Název"].strip() != '-' and ('reserved' not in row["Název"].strip().lower()) :
                    pprint ([row["Název"], row["Inv. č."]])
                    asset = Asset(
                        category=cat,
                        name=row["Název"].strip(),
                        manufacturer=row["Výrobce"].strip(),
                        note=row["Poznámka"].strip(),
                        custom_code=int(row["Inv. č."].replace(cat.prefix,"")),
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



