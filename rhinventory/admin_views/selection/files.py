from datetime import datetime

from flask import Response, abort
from flask_admin import expose

from rhinventory.admin_views.asset_files.stream_asset_files_zip import stream_asset_files_zip
from rhinventory.admin_views.utils import get_asset_list_from_request_args
from rhinventory.models.asset import Asset
from rhinventory.util import require_write_access


class BulkFileDownloadMixin:
    @expose('/download_files/', methods=['GET'])
    @require_write_access
    def download_files(self) -> Response:
        assets: list[Asset] = get_asset_list_from_request_args()
        if not assets:
            abort(404)

        zip_filename = f"asset_files_{datetime.utcnow():%Y-%m-%d}.zip"
        return Response(
            stream_asset_files_zip(assets),
            mimetype='application/zip',
            headers={'Content-Disposition': f'attachment; filename="{zip_filename}"'},
        )
