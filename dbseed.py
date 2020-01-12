from sys import argv
import csv
from datetime import datetime
from decimal import Decimal
from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.db import Asset
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
            pprint(row)
            asset = Asset(
                
            )

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



