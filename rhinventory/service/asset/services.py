from sqlalchemy import select
from sqlalchemy.orm import Session, Query

from rhinventory.api.asset.schemas import AssetSchema
from rhinventory.models.asset import Asset
from rhinventory.models.asset_attributes import AssetTag, asset_tag_table
from rhinventory.models.enums import HIDDEN_PRIVACIES, PUBLIC_PRIVACIES
from rhinventory.util import print_sql_query


class InvalidAssetTag(Exception):
    """Tag doesn't exist or is otherwise invalid."""
    pass


class AssetService:

    @staticmethod
    def _ensure_privacy(query: Query, private: bool) -> Query:
        """
        Adds where clause, to respect Asset privacy settings.

        :param query: given query on Asset
        :param private: If True, shows event private items, otherwise only public.
        :return: modified query
        """
        return query.where(Asset.privacy.in_(PUBLIC_PRIVACIES if not private else PUBLIC_PRIVACIES + HIDDEN_PRIVACIES))

    @staticmethod
    def list_all(db_session: Session, limit: int = 100, offset: int = 0, private=False):
        """
        List all Assets.

        Respects publicity of given assets.

        :param limit: How much assets to return (defaut 100).
        :param offset: With what offset (defaults to 0).
        :param private: If True, shows even private items (defaults to False).
        :return: List of Asset objects.
        """
        query = select(Asset).limit(limit).offset(offset)
        query = AssetService._ensure_privacy(query, private)

        assets = db_session.execute(
            query
        )

        return [asset[0] for asset in assets.fetchall()]

    @staticmethod
    def list_by_tag(db_session: Session, tag: str, limit: int = 100, offset: int = 0, private=False):
        """
        List all assets with concrete tag.

        Respects publicity of given assets.

        :param tag: Concrete Asset tag.
        :param limit: How much assets to return (defaut 100).
        :param offset: With what offset (defaults to 0).
        :param private: If True, shows even private items (defaults to False).
        :return: List of Asset objects with given tag.
        """

        query = (
            select(Asset)
            .join(asset_tag_table, asset_tag_table.c.asset_id == Asset.id)
            .join(AssetTag, AssetTag.id == asset_tag_table.c.assettag_id)
            .where(AssetTag.name == tag)
            .limit(limit).offset(offset)
        )
        query = AssetService._ensure_privacy(query, private)

        assets = db_session.execute(
            query
        )

        return [asset[0] for asset in assets.fetchall()]
