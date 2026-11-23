from flask import Response
from flask_admin import expose

from rhinventory.admin_views.selection.attribute import add_attribute_bulk, attribute_choices
from rhinventory.models.asset_attributes import Platform
from rhinventory.util import require_write_access


class AddPlatformMixin:
    def selection_platform_choices(self) -> list[dict[str, int | str]]:
        """Platforms offered by the selection panel's platform picker, most recently used first."""
        return attribute_choices(Platform)

    @expose('/add_platform_bulk/', methods=['POST'])
    @require_write_access
    def add_platform_bulk(self) -> Response:
        """Add one platform to the selected assets.

        The platform is given either as `platform_id`, or as `new_platform_name`,
        which reuses an existing platform of that name (case-insensitive) or
        creates a new one.
        """
        return add_attribute_bulk(Platform, 'platforms', 'platform', create=Platform.from_name)
