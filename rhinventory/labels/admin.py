from flask import abort
from flask_admin import expose

from rhinventory.db import Asset
from rhinventory.extensions import db
from rhinventory.labels.labels import LabelLogo, LabelSize, label_variant
from rhinventory.util import require_write_access

SIZE_NAMES = {
    LabelSize.STANDARD: "Standard",
    LabelSize.SMALL: "Small",
    LabelSize.BIG: "Big",
}

LOGO_NAMES = {
    LabelLogo.RH: "RH",
    LabelLogo.HA: "HA",
    LabelLogo.UCM: "UCM",
}


class LabelsMixin:
    """The asset's labels page, on AssetView for the asset menu bar.

    Its template is in this package's blueprint.
    """

    @expose('/<int:id>/labels/')
    @require_write_access
    def labels_view(self, id: int):
        asset = db.session.get(Asset, id)
        if asset is None:
            abort(404)

        return self.render('labels/asset.html',
                           model=asset,
                           size_names=SIZE_NAMES,
                           logo_names=LOGO_NAMES,
                           variants={(size, logo): label_variant(size, logo)
                                     for size in LabelSize for logo in LabelLogo})
