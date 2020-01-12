from sys import argv
import csv
from datetime import datetime
from decimal import Decimal
from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.db import Asset, Category
import json
from pprint import pprint


csv_file = {
    'games':'/mnt/z/GM.csv'
}

app=create_app()
with app.app_context(): 

    with open (csv_file['games'], newline='') as f:
        reader = csv.reader(f)

        header = next(reader)

        for row in reader:
            row = dict(zip(header, row))
            asset = Asset(
                name=row["Název"],
                manufacturer=row["Výrobce"],
                note=row["Poznámka"],
                custom_code=int(row["Inv. č."].replace("GM","")),
                category=Category.query.filter(Category.prefix=='GM')
                
            )
            pprint(Asset)

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



