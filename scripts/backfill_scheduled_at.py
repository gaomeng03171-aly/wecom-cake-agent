"""Backfill scheduled_at for orders with an explicit annotated pickup date."""

import argparse
import re
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import get_settings
from app.db import get_session_factory
from app.models import Order
from app.services.order_requirements import parse_order_datetime


EXPLICIT_DATE = re.compile(r"^\(\d{1,2}\.\d{1,2}\)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill order.scheduled_at from explicit pickup dates."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write updates. Without this flag only prints candidates.",
    )
    args = parser.parse_args()

    settings = get_settings()
    timezone = ZoneInfo(settings.app_timezone)
    updated = 0

    with get_session_factory()() as db:
        orders = list(
            db.scalars(
                select(Order)
                .where(Order.scheduled_at.is_(None))
                .order_by(Order.id)
            ).all()
        )
        for order in orders:
            value = (
                order.requirements.get("pickup_time")
                or order.requirements.get("delivery_time")
            )
            if not isinstance(value, str) or not EXPLICIT_DATE.match(value):
                continue
            base_date = order.business_date
            if base_date is None:
                continue
            parsed = parse_order_datetime(
                value,
                datetime.combine(base_date, time(hour=9), tzinfo=timezone),
            )
            if parsed is None:
                continue
            print(
                order.id,
                f"{order.business_date:%m.%d}",
                value,
                "->",
                parsed.isoformat(),
            )
            if args.execute:
                order.scheduled_at = parsed
            updated += 1

        if args.execute:
            db.commit()

    print(
        f"{'updated' if args.execute else 'matched'}={updated}"
    )
    if not args.execute:
        print("Dry run only. Re-run with --execute to update.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
