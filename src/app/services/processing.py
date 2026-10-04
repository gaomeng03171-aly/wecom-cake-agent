from collections import Counter

from sqlalchemy.orm import Session

from app.schemas.activity import (
    ActivityParticipantOut,
    DinnerActivityOut,
    DinnerProposalOut,
    OutboxMessageOut,
    VoteOut,
)
from app.schemas.wecom import WeComMessageIn, WeComMessageReceiveResponse
from app.services.activities import create_activity_from_message, find_active_activity
from app.services.dify import DifyServiceError, analyze_dinner_message
from app.services.inbound import receive_message
from app.services.participants import apply_preferences_from_message
from app.services.proposals import (
    ProposalServiceError,
    cast_vote,
    confirm_activity,
    generate_proposals,
    list_proposals,
    list_votes,
    start_voting,
)
from app.services.outbox import dispatch_message, enqueue_reply


def process_inbound_message(
    db: Session,
    payload: WeComMessageIn,
    dispatch: bool = True,
) -> WeComMessageReceiveResponse:
    stored = receive_message(db, payload, commit=False)
    if stored.duplicate:
        return stored

    try:
        analysis = analyze_dinner_message(payload.content)
    except DifyServiceError as exc:
        outbox = enqueue_reply(
            db,
            payload.group_id,
            "我暂时无法理解这条消息，请稍后再试。",
            commit=False,
        )
        db.commit()
        db.refresh(outbox)
        if dispatch:
            outbox = dispatch_message(db, outbox.id)
        return stored.model_copy(
            update={
                "dify_error": str(exc),
                "outbox": OutboxMessageOut.model_validate(outbox),
            }
        )

    if analysis.intent == "unknown":
        local_intent = _infer_local_intent(payload.content)
        if local_intent is not None:
            analysis = analysis.model_copy(update={"intent": local_intent})

    activity = None
    participant = None
    proposals: list[DinnerProposalOut] = []
    vote = None
    error = None
    vote_summary = None
    confirmation = None

    if analysis.intent == "create_dinner":
        activity = create_activity_from_message(
            db,
            payload,
            analysis,
            commit=False,
        )
    elif analysis.intent == "provide_preference":
        activity = find_active_activity(db, payload.group_id)
        if activity is None:
            activity = create_activity_from_message(
                db,
                payload,
                analysis,
                commit=False,
            )
        participant = apply_preferences_from_message(
            db,
            activity.id,
            payload.sender_id,
            payload.sender_name,
            analysis,
            commit=False,
        )
    elif analysis.intent == "generate_proposals":
        activity = find_active_activity(db, payload.group_id)
        if activity is None:
            error = "no active activity"
        else:
            try:
                activity, generated = generate_proposals(
                    db,
                    activity.id,
                    commit=False,
                )
                if activity.status == "proposing":
                    activity = start_voting(
                        db,
                        activity.id,
                        commit=False,
                    )
                proposals = [
                    DinnerProposalOut.model_validate(item) for item in generated
                ]
            except ProposalServiceError as exc:
                error = str(exc)
    elif analysis.intent == "vote":
        activity = find_active_activity(db, payload.group_id)
        if activity is None or analysis.proposal_choice is None:
            error = "no active activity or missing proposal choice"
        elif _is_third_party_vote(payload.content):
            error = "member needs to vote directly"
        else:
            try:
                activity_proposals = list_proposals(db, activity.id)
                choice_index = analysis.proposal_choice - 1
                if choice_index < 0 or choice_index >= len(activity_proposals):
                    raise ProposalServiceError("proposal choice is out of range")
                participant = apply_preferences_from_message(
                    db,
                    activity.id,
                    payload.sender_id,
                    payload.sender_name,
                    analysis,
                    commit=False,
                )
                vote = cast_vote(
                    db,
                    activity.id,
                    payload.sender_id,
                    payload.sender_name,
                    activity_proposals[choice_index].id,
                    commit=False,
                )
            except ProposalServiceError as exc:
                error = str(exc)
    elif analysis.intent == "summarize":
        activity = find_active_activity(db, payload.group_id)
        if activity is None:
            error = "no active activity"
        else:
            try:
                vote_summary = _format_vote_summary(db, activity)
            except ProposalServiceError as exc:
                error = str(exc)
    elif analysis.intent == "confirm":
        activity = find_active_activity(db, payload.group_id)
        if activity is None:
            error = "no active activity"
        else:
            try:
                if activity.status != "confirmed":
                    activity = confirm_activity(
                        db,
                        activity.id,
                        commit=False,
                    )
                confirmation = _format_confirmation(db, activity)
            except ProposalServiceError as exc:
                error = str(exc)

    if error is not None:
        if error == "member needs to vote directly":
            reply = "投票需要成员本人 @我发送，例如“@机器人 我选2”。"
        else:
            reply = "暂时无法处理这条消息，请稍后再试。"
    elif confirmation is not None:
        reply = confirmation
    elif vote_summary is not None:
        reply = vote_summary
    elif proposals:
        reply = _format_proposals_reply(proposals)
    else:
        reply = analysis.reply
    outbox = enqueue_reply(
        db,
        payload.group_id,
        reply,
        activity_id=activity.id if activity else None,
        commit=False,
    )
    db.commit()
    db.refresh(outbox)
    if dispatch:
        outbox = dispatch_message(db, outbox.id)

    return stored.model_copy(
        update={
            "analysis": analysis,
            "activity": DinnerActivityOut.model_validate(activity) if activity else None,
            "participant": (
                ActivityParticipantOut.model_validate(participant)
                if participant
                else None
            ),
            "proposals": proposals,
            "vote": VoteOut.model_validate(vote) if vote else None,
            "dify_error": error,
            "outbox": OutboxMessageOut.model_validate(outbox),
        }
    )


def _format_proposals_reply(proposals: list[DinnerProposalOut]) -> str:
    lines = [f"我生成了 {len(proposals)} 个聚餐方案："]
    for index, proposal in enumerate(proposals, start=1):
        details = [proposal.proposed_time or "时间待定"]
        if proposal.budget_estimate is not None:
            details.append(f"预算约 {proposal.budget_estimate} 元")
        lines.append(
            f"{index}. {proposal.title}（{'，'.join(details)}）"
        )
    lines.append("请回复“我选1”“我选2”或“我选3”进行投票。")
    return "\n".join(lines)


def _infer_local_intent(content: str) -> str | None:
    normalized = content.strip()
    if any(
        keyword in normalized
        for keyword in ("确认方案", "确认结果", "确定方案", "就这个", "定下来")
    ):
        return "confirm"
    if any(
        keyword in normalized
        for keyword in ("总结", "汇总", "投票结果", "方案结果", "整理一下", "梳理")
    ):
        return "summarize"
    return None


def _is_third_party_vote(content: str) -> bool:
    return any(
        keyword in content
        for keyword in ("另一个成员", "其他人", "别人", "她选", "他选", "他们说", "她们选")
    )


def _format_vote_summary(db: Session, activity) -> str:
    proposals = list_proposals(db, activity.id)
    if not proposals:
        raise ProposalServiceError("no proposals available")

    votes = list_votes(db, activity.id)
    counts = Counter(vote.proposal_id for vote in votes)
    lines = ["当前投票结果："]
    for index, proposal in enumerate(proposals, start=1):
        voters = [
            vote.user_name or vote.user_id
            for vote in votes
            if vote.proposal_id == proposal.id
        ]
        voter_text = f"（{'、'.join(voters)}）" if voters else ""
        lines.append(
            f"{index}. {proposal.title}：{counts.get(proposal.id, 0)} 票{voter_text}"
        )

    if not votes:
        lines.append("目前还没有成员完成投票。")
        lines.append("请成员直接回复“我选1/2/3”参加投票。")
        return "\n".join(lines)

    leading_proposal_id = max(
        counts,
        key=lambda proposal_id: (counts[proposal_id], -proposal_id),
    )
    leading = next(
        proposal
        for proposal in proposals
        if proposal.id == leading_proposal_id
    )
    lines.append(f"目前领先：{leading.title}。")
    lines.append("确认最终方案请回复“确认方案”。")
    return "\n".join(lines)


def _format_confirmation(db: Session, activity) -> str:
    proposals = list_proposals(db, activity.id)
    proposal = next(
        (
            item
            for item in proposals
            if item.title == activity.confirmed_plan
        ),
        None,
    )
    lines = [
        "最终方案已确认：",
        f"活动：{activity.title}",
        f"方案：{activity.confirmed_plan}",
    ]
    if proposal is not None:
        if proposal.proposed_time:
            lines.append(f"时间：{proposal.proposed_time}")
        if proposal.cuisine:
            lines.append(f"菜系：{proposal.cuisine}")
        if proposal.budget_estimate is not None:
            lines.append(f"预算：人均约 {proposal.budget_estimate} 元")
    lines.append("后续提醒会按这个方案安排。")
    return "\n".join(lines)
