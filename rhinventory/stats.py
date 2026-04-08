
from typing import TypedDict
import datetime

from sqlalchemy import func

from rhinventory.extensions import db
from rhinventory.db import LogItem, Asset, File
from rhinventory.models.enums import Privacy


PERIODS: list[tuple[str, datetime.timedelta | None]] = [
    ('24h', datetime.timedelta(hours=24)),
    ('7d', datetime.timedelta(days=7)),
    ('30d', datetime.timedelta(days=30)),
    ('365d', datetime.timedelta(days=365)),
    ('Total', None),
]

CATEGORIES: list[tuple[str, str]] = [
    ('Assets', 'Asset'),
    ('Files', 'File'),
]

EVENT_TYPES: list[tuple[str, str]] = [
    ('New', 'Create'),
    ('Changes', 'Update'),
]

PERIOD_LABELS: list[str] = [label for label, _ in PERIODS]
CATEGORY_LABELS: list[str] = [label for label, _ in CATEGORIES] + ['Other']
EVENT_TYPE_LABELS: list[str] = [label for label, _ in EVENT_TYPES]


EventTypeCounts = dict[str, int]
CategoryCounts = dict[str, EventTypeCounts]
StatsTable = dict[str, CategoryCounts]


class AssetChartData(TypedDict):
    labels: list[str]
    counts: list[int]
    cumulative: list[int]


class CurrentTotals(TypedDict):
    assets: int
    files: int


class LatestPublicAsset(TypedDict):
    id: int
    name: str


def get_stats_table() -> StatsTable:
    now = datetime.datetime.now()
    stats: StatsTable = {}
    for period_label, delta in PERIODS:
        since = (now - delta) if delta else None
        stats[period_label] = {}
        for cat_label, table_name in CATEGORIES:
            stats[period_label][cat_label] = {}
            for evt_label, evt_name in EVENT_TYPES:
                q = db.session.query(func.count(LogItem.id)).filter(
                    LogItem.table == table_name,
                    LogItem.event == evt_name,
                )
                if since:
                    q = q.filter(LogItem.datetime >= since)
                stats[period_label][cat_label][evt_label] = q.scalar()
        # Other: everything not in CATEGORIES
        stats[period_label]['Other'] = {}
        for evt_label, evt_name in EVENT_TYPES:
            q = db.session.query(func.count(LogItem.id)).filter(
                LogItem.table.notin_([table for _, table in CATEGORIES]),
                LogItem.event == evt_name,
            )
            if since:
                q = q.filter(LogItem.datetime >= since)
            stats[period_label]['Other'][evt_label] = q.scalar()
    return stats


def get_asset_chart_data() -> AssetChartData:
    month_col = func.date_trunc('month', LogItem.datetime)
    rows = (
        db.session.query(month_col.label('month'), func.count(LogItem.id))
        .filter(LogItem.table == 'Asset', LogItem.event == 'Create')
        .group_by(month_col)
        .order_by(month_col)
        .all()
    )
    labels = [r.month.strftime('%Y-%m') for r in rows]
    counts = [r[1] for r in rows]
    cumulative: list[int] = []
    total = 0
    for c in counts:
        total += c
        cumulative.append(total)
    return {'labels': labels, 'counts': counts, 'cumulative': cumulative}


def get_current_totals() -> CurrentTotals:
    return {
        'assets': db.session.query(func.count(Asset.id)).scalar(),
        'files': db.session.query(func.count(File.id)).scalar(),
    }


def get_latest_public_asset() -> LatestPublicAsset | None:
    asset = (
        db.session.query(Asset)
        .filter(Asset.privacy == Privacy.public)
        .order_by(Asset.made_public_at.desc())
        .first()
    )
    if asset is None:
        return None
    return {'id': asset.id, 'name': asset.name}
