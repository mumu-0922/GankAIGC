import math
import re
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.models import CreditCode, CreditTransaction, OptimizationSession, User


CREDIT_UNIT_CHARACTERS = 1000
PROCESSING_MODE_STAGE_MULTIPLIERS = {
    "paper_polish": 1,
    "paper_enhance": 1,
    "emotion_polish": 1,
    "paper_polish_enhance": 2,
}


def count_billable_characters(text: str) -> int:
    return len(re.findall(r"\S", text or ""))


def calculate_optimization_credits(text: str, processing_mode: str) -> int:
    billable_characters = count_billable_characters(text)
    base_credits = max(1, math.ceil(billable_characters / CREDIT_UNIT_CHARACTERS))
    stage_multiplier = PROCESSING_MODE_STAGE_MULTIPLIERS.get(processing_mode, 1)
    return base_credits * stage_multiplier


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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="扣除额度必须大于 0")

        current_balance = user.credit_balance or 0
        if not user.is_unlimited and current_balance < amount:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"平台剩余额度不足，本次需要 {amount} 额度，当前剩余 {current_balance} 额度",
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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="退回额度必须大于 0")

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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="充值额度必须大于 0")

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
        credit_code.redeemed_at = datetime.utcnow()
        return transaction
