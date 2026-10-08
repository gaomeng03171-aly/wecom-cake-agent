"""Remove legacy dinner data and incomplete orders without a business number."""

import argparse

from sqlalchemy import delete, func, select

from app.db import get_session_factory
from app.models import (
    ActivityParticipant,
    DinnerActivity,
    DinnerProposal,
    Order,
    OrderConfirmation,
    OrderQuote,
    OutboxMessage,
    Reminder,
    Vote,
)


def _count(db, model) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def _count_where(db, model, *conditions) -> int:
    statement = select(func.count()).select_from(model)
    if conditions:
        statement = statement.where(*conditions)
    return int(db.scalar(statement) or 0)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean dinner-era data and orders without order numbers."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete data. Without this flag only prints counts.",
    )
    args = parser.parse_args()

    with get_session_factory()() as db:
        legacy_order_ids = select(Order.id).where(Order.order_number.is_(None))
        activity_ids = select(DinnerActivity.id)
        counts = {
            "orders_without_number": _count_where(
                db,
                Order,
                Order.order_number.is_(None),
            ),
            "activity_rows": _count(db, DinnerActivity),
            "participant_rows": _count(db, ActivityParticipant),
            "proposal_rows": _count(db, DinnerProposal),
            "vote_rows": _count(db, Vote),
            "activity_reminder_rows": _count(db, Reminder),
            "activity_outbox_rows": _count_where(
                db,
                OutboxMessage,
                OutboxMessage.activity_id.is_not(None),
            ),
        }
        print(counts)

        if not args.execute:
            print("Dry run only. Re-run with --execute to delete.")
            return 0

        db.execute(
            delete(OrderQuote).where(
                OrderQuote.order_id.in_(legacy_order_ids)
            )
        )
        db.execute(
            delete(OrderConfirmation).where(
                OrderConfirmation.order_id.in_(legacy_order_ids)
            )
        )
        db.execute(delete(Order).where(Order.order_number.is_(None)))

        db.execute(
            delete(OutboxMessage).where(
                OutboxMessage.activity_id.is_not(None)
            )
        )
        db.execute(
            delete(Reminder).where(
                Reminder.activity_id.in_(activity_ids)
            )
        )
        db.execute(
            delete(Vote).where(
                Vote.activity_id.in_(activity_ids)
            )
        )
        db.execute(
            delete(DinnerProposal).where(
                DinnerProposal.activity_id.in_(activity_ids)
            )
        )
        db.execute(
            delete(ActivityParticipant).where(
                ActivityParticipant.activity_id.in_(activity_ids)
            )
        )
        db.execute(delete(DinnerActivity))
        db.commit()

        print(
            {
                "remaining_orders": _count(db, Order),
                "remaining_orders_without_number": _count_where(
                    db,
                    Order,
                    Order.order_number.is_(None),
                ),
                "remaining_activity_rows": _count(db, DinnerActivity),
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
