import math
import re
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.models import CreditCode, CreditTransaction, OptimizationSession, User
from app.utils.time import utcnow


CREDIT_UNIT_CHARACTERS = 1000
PROCESSING_MODE_STAGE_MULTIPLIERS = {
    "paper_polish": 1,
    "paper_enhance": 1,
    "emotion_polish": 1,
    "paper_polish_enhance": 2,
}

CREDIT_TRANSACTION_REASON_LABELS = {
    "redeem_code": "兑换码充值",
    "admin_recharge": "管理员充值",
    "optimization_start": "降 AI 消耗",
    "optimization_refund": "任务失败退款",
    "word_formatter_preprocess": "Word 预处理消耗",
    "word_formatter_preprocess_refund": "Word 预处理退款",
    "word_formatter_format": "Word 排版消耗",
    "word_formatter_format_refund": "Word 排版退款",
}


def count_billable_characters(text: str) -> int:
    return len(re.findall(r"\S", text or ""))


def calculate_optimization_credits(text: str, processing_mode: str) -> int:
    billable_characters = count_billable_characters(text)
    base_credits = max(1, math.ceil(billable_characters / CREDIT_UNIT_CHARACTERS))
    stage_multiplier = PROCESSING_MODE_STAGE_MULTIPLIERS.get(processing_mode, 1)
    return base_credits * stage_multiplier


def get_credit_transaction_reason_label(reason: str) -> str:
    return CREDIT_TRANSACTION_REASON_LABELS.get(reason, reason)


def get_credit_transaction_type(delta: int) -> str:
    if delta > 0:
        return "credit"
    if delta < 0:
        return "debit"
    return "neutral"


def serialize_credit_transaction(
    transaction: CreditTransaction,
    *,
    include_user: bool = False,
) -> dict:
    related_session = transaction.related_session
    payload = {
        "id": transaction.id,
        "delta": transaction.delta,
        "balance_after": transaction.balance_after,
        "reason": transaction.reason,
        "reason_label": get_credit_transaction_reason_label(transaction.reason),
        "transaction_type": get_credit_transaction_type(transaction.delta),
        "related_code_id": transaction.related_code_id,
        "related_session_id": transaction.related_session_id,
        "related_session_public_id": related_session.session_id if related_session else None,
        "related_session_title": related_session.task_title if related_session else None,
        "related_session_processing_mode": related_session.processing_mode if related_session else None,
        "created_at": transaction.created_at,
    }

    if include_user:
        user = transaction.user
        payload.update(
            {
                "user_id": transaction.user_id,
                "username": user.username if user else None,
                "nickname": user.nickname if user else None,
                "user_display_name": (
                    user.nickname or user.username or f"用户 #{user.id}"
                    if user
                    else "未知用户"
                ),
            }
        )

    return payload


class CreditService:
    def __init__(self, db: Session):
        self.db = db

    def hold_platform_credit(
        self,
        user: User,
        reason: str,
        session_id: int | None = None,
        amount: int = 1,
    ) -> CreditTransaction:
        if amount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="扣除啤酒必须大于 0")

        current_balance = user.credit_balance or 0
        if not user.is_unlimited and current_balance < amount:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"平台剩余啤酒不足，本次需要 {amount} 啤酒，当前剩余 {current_balance} 啤酒",
            )

        if user.is_unlimited:
            delta = 0
        else:
            user.credit_balance = current_balance - amount
            delta = -amount

        transaction = CreditTransaction(
            user_id=user.id,
            delta=delta,
            balance_after=user.credit_balance or 0,
            reason=reason,
            related_session_id=session_id,
        )
        self.db.add(transaction)
        return transaction

    def refund_platform_credit(
        self,
        user: User,
        reason: str,
        session_id: int | None = None,
        amount: int = 1,
    ) -> CreditTransaction:
        if amount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="退回啤酒必须大于 0")

        if user.is_unlimited:
            delta = 0
        else:
            user.credit_balance = (user.credit_balance or 0) + amount
            delta = amount

        transaction = CreditTransaction(
            user_id=user.id,
            delta=delta,
            balance_after=user.credit_balance or 0,
            reason=reason,
            related_session_id=session_id,
        )
        self.db.add(transaction)
        return transaction

    def refund_held_platform_credit(self, session: OptimizationSession) -> CreditTransaction | None:
        if session.billing_mode != "platform" or session.charge_status != "held" or session.charged_credits <= 0:
            return None

        user = self.db.query(User).filter(User.id == session.user_id).first()
        if not user:
            return None

        transaction = self.refund_platform_credit(
            user,
            reason="optimization_refund",
            session_id=session.id,
            amount=session.charged_credits,
        )
        session.charge_status = "refunded"
        session.charged_credits = 0
        return transaction

    def add_credits(
        self,
        user: User,
        amount: int,
        reason: str,
        code_id: int | None = None,
    ) -> CreditTransaction:
        if amount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="充值啤酒必须大于 0")

        user.credit_balance = (user.credit_balance or 0) + amount
        transaction = CreditTransaction(
            user_id=user.id,
            delta=amount,
            balance_after=user.credit_balance,
            reason=reason,
            related_code_id=code_id,
        )
        self.db.add(transaction)
        return transaction

    def redeem_code(self, user: User, code: str) -> CreditTransaction:
        now = datetime.now(timezone.utc)
        credit_code = (
            self.db.query(CreditCode)
            .filter(
                CreditCode.code == code,
                CreditCode.is_active.is_(True),
                CreditCode.redeemed_by_user_id.is_(None),
            )
            .first()
        )

        if not credit_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="兑换码无效")

        expires_at = credit_code.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and expires_at < now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="兑换码已过期")

        transaction = self.add_credits(
            user,
            credit_code.credit_amount,
            reason="redeem_code",
            code_id=credit_code.id,
        )
        credit_code.is_active = False
        credit_code.redeemed_by_user_id = user.id
        credit_code.redeemed_at = utcnow()
        return transaction
