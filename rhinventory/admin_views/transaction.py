import typing
from flask import request, redirect, url_for, flash, Response
from flask_admin import expose

from rhinventory.admin_views.model_view import CustomModelView
from rhinventory.admin_views.utils import get_asset_list_from_request_args

from rhinventory.extensions import db
from rhinventory.models.transaction import Transaction
from rhinventory.util import require_write_access


class TransactionView(CustomModelView):
    can_view_details = True
    column_default_sort = ('id', True)
    column_list = ('id', 'date', 'finalized', 'transaction_type', 'counterparty_new', 'assets')
    form_columns = [
        'our_party',
        'counterparty_new',
        'transaction_type',
        'cost',
        'assets',
        'date',
        'url',
        'note',
        'penouze_id',
        'finalized',
    ]
    column_filters = [
        'transaction_type',
        'finalized',
        'our_party',
        'counterparty_new',
    ]
    column_searchable_list = [
        'id',
        'penouze_id',
        #'our_party',
        #'counterparty_new',
        'url',
        'note',
    ]
    details_template = "admin/transaction/details.html"

    def create_form(self, obj=None):
        form = super(TransactionView, self).create_form()

        # second condition forces program to not overwrite data that has been
        # sent by user. If data has been sent, `form.assets.data` is already filled
        # with appropriate stuff and thus, you must not overwrite it
        assets = get_asset_list_from_request_args()
        if assets and len(form.assets.data) == 0:
            form.assets.data = assets

        return form

    @expose('/add_to/', methods=['POST'])
    @require_write_access
    def add_to_view(self) -> Response:
        transaction_id = int(request.form['transaction_id'])
        transaction: Transaction
        transaction = db.session.query(Transaction).get(transaction_id)
        if not transaction:
            flash(f"Transaction with id {transaction_id} not found.", 'error')
            return redirect(url_for('.index_view'))

        assert transaction

        assets = get_asset_list_from_request_args()
        transaction.assets += assets
        db.session.add(transaction)
        db.session.commit()

        message = f"{len(assets)} assets added to transaction and saved."
        if not transaction.finalized:
            message += "\nWould you like to mark it as finalized?"

        flash(message, "success")

        return redirect(url_for('.edit_view', id=transaction_id))


        