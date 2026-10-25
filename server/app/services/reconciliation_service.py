"""Reconciliation: resolve stale payments and payouts against Paystack, and check the ledger's invariants.

``run`` asks Paystack about top-ups and payouts that are still open after RECONCILE_AFTER_MINUTES and applies
the answer through the same code as webhooks. ``report`` never changes anything; it lists discrepancies:

* a wallet balance that differs from its ledger (settled credits minus pending and settled debits);
* a charge whose debit differs from its provider credit plus platform fee, or that lacks its debit;
* a SUCCEEDED top-up without exactly one matching deposit, or a deposit for a payment that did not succeed;
* a payout whose hold does not match its state;
* a refund whose ledger entries do not match it, a charge refunded more than it cost, or a top-up refunded more
  than it paid.
"""

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any

from app.core.config import settings
from app.core.database import Session, session_scope
from app.core.timeutil import utcnow
from app.documents.billing import Charge, Payment, PaymentStatus, Payout, PayoutStatus, Refund, RefundKind, RefundStatus
from app.documents.transaction import Transaction, TransactionStatus, TransactionType
from app.documents.wallet import Wallet
from app.services import payments_service, paystack, refund_service
from app.services.ledger_service import DEBIT_STATES, money
from app.services.paystack import PaystackError

logger = logging.getLogger(__name__)

HOLD_FOR = {
    PayoutStatus.REQUESTED.value: TransactionStatus.PENDING.value,
    PayoutStatus.PENDING.value: TransactionStatus.PENDING.value,
    PayoutStatus.OTP_REQUIRED.value: TransactionStatus.PENDING.value,
    PayoutStatus.SUCCEEDED.value: TransactionStatus.SETTLED.value,
    PayoutStatus.FAILED.value: TransactionStatus.FAILED.value,
    PayoutStatus.REVERSED.value: TransactionStatus.FAILED.value,
    PayoutStatus.REJECTED.value: TransactionStatus.FAILED.value,
}


async def run(now=None) -> dict[str, Any]:
    """Settle stale open items with Paystack. Each item is its own transaction."""
    if not settings.payments_enabled:
        return {"skipped": "payments not configured"}
    now = now or utcnow()
    cutoff = now - timedelta(minutes=settings.RECONCILE_AFTER_MINUTES)
    results: dict[str, Any] = {"payments": {}, "payouts": {}, "errors": 0}
    async with session_scope() as db:
        payment_refs = [
            p.reference
            for p in await db.find(Payment, {"status": PaymentStatus.INITIALIZED.value, "created_at": {"$lt": cutoff}})
        ]
        payout_refs = [
            p.reference
            for p in await db.find(
                Payout,
                {
                    "status": {"$in": [PayoutStatus.PENDING.value, PayoutStatus.OTP_REQUIRED.value]},
                    "updated_at": {"$lt": cutoff},
                },
            )
        ]
        unconfirmed = [
            p.reference
            for p in await db.find(
                Payout,
                {
                    "status": {
                        "$in": [PayoutStatus.SUCCEEDED.value, PayoutStatus.FAILED.value, PayoutStatus.REVERSED.value]
                    },
                    "transfer_code": {"$ne": None},
                    "reconciled_at": None,
                },
            )
        ]
    for ref in payment_refs:
        async with session_scope() as db:
            payment = await db.find_one(Payment, {"reference": ref})
            if payment is None:
                continue
            try:
                data = await paystack.verify_transaction(ref)
            except PaystackError as exc:
                if exc.status == 404 or "not found" in str(exc).lower():
                    data = {"status": "abandoned", "gateway_response": "Checkout was never completed"}
                else:
                    results["errors"] += 1
                    continue
            outcome = await payments_service.apply_paystack_result(db, payment, data, source="reconciliation")
            await db.commit()
            results["payments"][ref] = outcome
    for ref in [*payout_refs, *unconfirmed]:
        async with session_scope() as db:
            payout = await db.find_one(Payout, {"reference": ref})
            if payout is None:
                continue
            try:
                data = await paystack.verify_transfer(ref)
            except PaystackError as exc:
                if (
                    exc.status == 404 or "not found" in str(exc).lower()
                ) and payout.status == PayoutStatus.PENDING.value:
                    # Paystack has no such transfer: it was never created, so the held funds go back.
                    data = {"status": "failed", "reason": "Transfer was not created at Paystack"}
                else:
                    results["errors"] += 1
                    continue
            outcome = await payments_service.apply_transfer_result(db, payout, data)
            await db.refresh(payout)
            remote = str(data.get("status") or "")
            local = {"success": "SUCCEEDED", "failed": "FAILED", "reversed": "REVERSED"}.get(remote)
            if local == payout.status:
                payout.reconciled_at = utcnow()
                outcome = f"{outcome}; reconciled"
            elif local and payout.status in HOLD_FOR and payout.status not in payments_service.OPEN_PAYOUT:
                outcome = f"MISMATCH: AgentMesh says {payout.status}, Paystack says {remote}"
                logger.error("Payout %s %s", ref, outcome)
            await db.commit()
            results["payouts"][ref] = outcome
    async with session_scope() as db:
        stale_refunds = [
            r.id
            for r in await db.find(
                Refund,
                {"kind": RefundKind.TOPUP.value, "status": RefundStatus.PENDING.value, "created_at": {"$lt": cutoff}},
            )
        ]
    results["refunds"] = {}
    for refund_id in stale_refunds:
        async with session_scope() as db:
            refund = await db.get(Refund, refund_id)
            if refund is None or not refund.paystack_refund_id:
                if refund is not None:
                    results["refunds"][refund.reference] = "unverifiable: no Paystack refund id"
                continue
            try:
                data = await paystack.fetch_refund(refund.paystack_refund_id)
            except PaystackError:
                results["errors"] += 1
                continue
            results["refunds"][refund.reference] = await refund_service.apply_paystack_result(db, refund, data)
            await db.commit()
    return results


async def _sums(db: Session, match: dict[str, Any], *group: str) -> dict[Any, tuple[int, Decimal]]:
    """(count, summed amount) of ledger entries matching ``match``, grouped by the given fields."""
    key: Any = {g: f"${g}" for g in group} if len(group) > 1 else f"${group[0]}"
    rows = await db.aggregate(
        Transaction,
        [{"$match": match}, {"$group": {"_id": key, "n": {"$sum": 1}, "amount": {"$sum": "$amount"}}}],
    )
    out: dict[Any, tuple[int, Decimal]] = {}
    for r in rows:
        k = tuple(r["_id"].get(g) for g in group) if len(group) > 1 else r["_id"]
        out[k] = (int(r["n"]), money(r["amount"] or 0))
    return out


HOLD_FOR_REFUND = {
    RefundStatus.PENDING.value: TransactionStatus.PENDING.value,
    RefundStatus.SUCCEEDED.value: TransactionStatus.SETTLED.value,
    RefundStatus.FAILED.value: TransactionStatus.FAILED.value,
}


async def _refund_issues(db: Session, charges: list[Charge]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    postings = {
        k: a for k, (_, a) in (await _sums(db, {"reference": {"$regex": "^am-rf-"}}, "reference", "type")).items()
    }
    holds = {t.reference: t.status for t in await db.find(Transaction, {"type": TransactionType.TOPUP_REFUND.value})}

    def posted(refund: Refund, type_: TransactionType) -> Decimal:
        return postings.get((refund.reference, type_.value), Decimal(0))

    by_charge: dict[Any, Decimal] = {}
    by_payment: dict[Any, Decimal] = {}
    for r in await db.find(Refund):
        amount = money(r.amount)
        if r.kind == RefundKind.CHARGE.value:
            by_charge[r.charge_id] = by_charge.get(r.charge_id, Decimal(0)) + amount
            if (
                posted(r, TransactionType.REFUND) != amount
                or posted(r, TransactionType.REFUND_CLAWBACK) != money(r.provider_amount)
                or posted(r, TransactionType.PLATFORM_FEE_REVERSAL) != money(r.platform_fee)
                or money(r.provider_amount) + money(r.platform_fee) != amount
            ):
                issues.append({"kind": "refund_postings", "reference": r.reference, "amount": str(amount)})
            continue
        if holds.get(r.reference) != HOLD_FOR_REFUND[r.status] or posted(r, TransactionType.TOPUP_REFUND) != amount:
            issues.append({"kind": "refund_hold", "reference": r.reference, "status": r.status})
        if r.status != RefundStatus.FAILED.value:
            by_payment[r.payment_id] = by_payment.get(r.payment_id, Decimal(0)) + amount
        if r.status == RefundStatus.PENDING.value and not r.paystack_refund_id:
            issues.append({"kind": "refund_unverifiable", "reference": r.reference})
    for c in charges:
        refunded = money(c.refunded_amount or 0)
        if refunded != by_charge.get(c.id, Decimal(0)) or refunded > money(c.amount):
            issues.append({"kind": "charge_refunds", "charge_id": str(c.id), "refunded": str(refunded)})
    for payment in await db.find(Payment, {"_id": {"$in": list(by_payment)}}):
        if by_payment[payment.id] > money(payment.amount):
            issues.append({"kind": "topup_over_refunded", "reference": payment.reference})
    return issues


async def report(db: Session) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []

    credits = await _sums(db, {"to_wallet": {"$ne": None}, "status": TransactionStatus.SETTLED.value}, "to_wallet")
    debits = await _sums(db, {"from_wallet": {"$ne": None}, "status": {"$in": list(DEBIT_STATES)}}, "from_wallet")
    # Stored balances as they are now, not as loaded earlier into this session.
    wallets = await db.aggregate(Wallet, [{"$project": {"user_id": 1, "balance": 1}}])
    for wallet in wallets:
        expected = money(credits.get(wallet["_id"], (0, Decimal(0)))[1] - debits.get(wallet["_id"], (0, Decimal(0)))[1])
        balance = money(wallet.get("balance") or 0)
        if balance != expected:
            issues.append(
                {
                    "kind": "wallet_balance",
                    "wallet_id": str(wallet["_id"]),
                    "user_id": str(wallet.get("user_id")),
                    "balance": str(balance),
                    "ledger": str(expected),
                }
            )

    posted = {
        k: a for k, (_, a) in (await _sums(db, {"reference": {"$regex": "^charge:"}}, "reference", "type")).items()
    }
    charges = await db.find(Charge)
    for c in charges:
        key = f"charge:{c.id}"
        debit = posted.get((key, TransactionType.COMPUTE_CHARGE.value), Decimal(0))
        credit = posted.get((key, TransactionType.PROVIDER_CREDIT.value), Decimal(0))
        fee = posted.get((key, TransactionType.PLATFORM_FEE.value), Decimal(0))
        if (
            money(debit) != money(c.amount)
            or money(credit + fee) != money(debit)
            or money(c.provider_amount + c.platform_fee) != money(c.amount)
        ):
            issues.append(
                {
                    "kind": "charge_split",
                    "charge_id": str(c.id),
                    "amount": str(c.amount),
                    "debited": str(debit),
                    "credited": str(credit),
                    "fee": str(fee),
                }
            )

    deposits = await _sums(
        db, {"type": TransactionType.DEPOSIT.value, "reference": {"$regex": "^am-top-"}}, "reference"
    )
    for p in await db.find(Payment):
        n, amount = deposits.get(p.reference, (0, Decimal(0)))
        if p.status == PaymentStatus.SUCCEEDED.value and (n != 1 or money(amount) != money(p.amount)):
            issues.append({"kind": "payment_not_credited_once", "reference": p.reference, "deposits": n})
        if p.status != PaymentStatus.SUCCEEDED.value and n:
            issues.append({"kind": "deposit_without_success", "reference": p.reference, "status": p.status})
        if p.status == PaymentStatus.REVIEW.value:
            issues.append({"kind": "payment_needs_review", "reference": p.reference, "reason": p.failure_reason})

    for po in await db.find(Payout):
        hold = await db.get(Transaction, po.transaction_id) if po.transaction_id else None
        want = HOLD_FOR.get(po.status)
        if hold is None or hold.status != want or money(hold.amount) != money(po.amount):
            issues.append(
                {
                    "kind": "payout_hold",
                    "reference": po.reference,
                    "status": po.status,
                    "hold_status": hold.status if hold else None,
                }
            )

    issues += await _refund_issues(db, charges)

    open_counts = {
        "payments_initialized": await db.count(Payment, {"status": PaymentStatus.INITIALIZED.value}),
        "payouts_awaiting_approval": await db.count(Payout, {"status": PayoutStatus.REQUESTED.value}),
        "refunds_in_flight": await db.count(Refund, {"status": RefundStatus.PENDING.value}),
        "payouts_in_flight": await db.count(
            Payout, {"status": {"$in": [PayoutStatus.PENDING.value, PayoutStatus.OTP_REQUIRED.value]}}
        ),
    }
    return {
        "ok": not issues,
        "issues": issues,
        "checked": {"wallets": len(wallets), "charges": len(charges)},
        "open": open_counts,
        "generated_at": utcnow(),
    }
