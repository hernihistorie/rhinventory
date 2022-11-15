from flask import request

from rhinventory.admin_views.model_view import CustomModelView

from rhinventory.extensions import simple_eval
from rhinventory.db import Asset

class TransactionView(CustomModelView):
    can_view_details = True
    column_default_sort = ('id', True)
    column_list = ('id', 'date', 'transaction_type', 'counterparty', 'assets')
    form_columns = [
        'our_party',
        'counterparty_new',
        'transaction_type',
        'cost',
        'date',
        'url',
        'note',
        'penouze_id',
    ]
    details_template = "admin/transaction/details.html"

    def create_form(self, obj=None):
        form = super(TransactionView, self).create_form()

        # second condition forces program to not overwrite data that has been
        # sent by user. If data has been sent, `form.assets.data` is already filled
        # with appropriate stuff and thus, you must not overwrite it
        if "asset_id" in request.args.keys() and len(form.assets.data) == 0:
            asset_id = simple_eval.eval(request.args["asset_id"])
            if isinstance(asset_id, list):
                asset_query = self.session.query(Asset).filter(Asset.id.in_(asset_id)).all()
                form.assets.data = asset_query
            else:
                asset_query = self.session.query(Asset).filter(Asset.id == asset_id).one()
                form.assets.data = [asset_query]

        return form