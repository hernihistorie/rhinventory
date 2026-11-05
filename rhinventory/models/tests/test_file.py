import pytest

from rhinventory.models.file import File, FileCategory, FileStore


@pytest.mark.parametrize("filename, asset_id", [
    ("hh10461.jpg", 10461),
    ("hh10480.jpg", 10480),
    ("hh10509.jpg", 10509),
])
def test_read_rh_barcode(app, zbar, test_photos_dir, filename, asset_id):
    app.config['FILE_STORE_LOCATIONS'] = {"local": str(test_photos_dir)}

    with app.app_context():
        file = File(
            filepath=filename,
            storage=FileStore.local,
            category=FileCategory.image,
        )
        assert file.read_rh_barcode() == asset_id
