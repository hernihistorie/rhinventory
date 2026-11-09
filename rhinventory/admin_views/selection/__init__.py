"""Actions in the asset list's selection panel.

Each action is a tab in the panel. Its route (if it needs one) is a mixin in a
module here, and its tab is `templates/selection/<name>.html`, which defines
three macros that `admin/asset/list.html` renders:

- `label()`: the tab's title
- `pane()`: the tab's content
- `script()`: its JS, run after the shared selection script, so it can use
  `selection`, `takeSelection()` and `submitWithSelection()` from there, and
  listen for the `assetselectionchange` event on `document`.

The tab order is the `selection_actions` list in `list.html`.
"""
from flask import Blueprint

from rhinventory.admin_views.selection.files import BulkFileDownloadMixin
from rhinventory.admin_views.selection.location import SetLocationMixin
from rhinventory.admin_views.selection.parent import SetParentMixin
from rhinventory.admin_views.selection.tag import AddTagMixin

# Only makes this directory's templates available.  The routes stay on AssetView.
selection_bp = Blueprint('selection', __name__, template_folder='templates')


class SelectionActionsMixin(BulkFileDownloadMixin, SetParentMixin, SetLocationMixin, AddTagMixin):
    pass
