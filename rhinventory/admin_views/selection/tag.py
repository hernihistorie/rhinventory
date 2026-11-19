from flask import Response
from flask_admin import expose

from rhinventory.admin_views.selection.attribute import add_attribute_bulk, attribute_choices
from rhinventory.models.asset_attributes import AssetTag
from rhinventory.util import require_write_access


class AddTagMixin:
    def selection_tag_choices(self) -> list[dict[str, int | str]]:
        """Tags offered by the selection panel's tag picker, most recently used first."""
        return attribute_choices(AssetTag)

    @expose('/add_tag_bulk/', methods=['POST'])
    @require_write_access
    def add_tag_bulk(self) -> Response:
        """Add one tag to the selected assets.

        The tag is given either as `tag_id`, or as `new_tag_name`, which reuses
        an existing tag of that name (case-insensitive) or creates a new one.
        """
        return add_attribute_bulk(AssetTag, 'tags', 'tag')
