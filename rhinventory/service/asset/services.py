from sqlalchemy import select
from sqlalchemy.orm import Session

from rhinventory.api.asset.schemas import AssetSchema
from rhinventory.models.asset import Asset
from rhinventory.models.enums import HIDDEN_PRIVACIES, PUBLIC_PRIVACIES


class AssetService:
    @staticmethod
    def list_all(db_session: Session, limit: int = 100, offset: int = 0, private=False):
        """
        List all Assets.

        :param limit: How much assets to return (defaut 100).
        :param offset: With what offset (defaults to 0).
        :param private: If True, shows even private items (defaults to False).
        :return: List of Asset objects.
        """

        assets = db_session.execute(
            select(Asset)
            .where(Asset.privacy.in_(PUBLIC_PRIVACIES if not private else PUBLIC_PRIVACIES + HIDDEN_PRIVACIES))
            .limit(limit).offset(offset)
        )

        return [asset[0] for asset in assets.fetchall()]
