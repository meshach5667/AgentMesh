import pytest
import uuid
from decimal import Decimal
from app.services.payment_service import PLATFORM_FEE_RATE

def test_platform_fee_rate():
    assert PLATFORM_FEE_RATE == Decimal("0.10")

def test_fee_calculation():
    cost = Decimal("100.00")
    fee = cost * PLATFORM_FEE_RATE
    provider_credit = cost - fee
    assert fee == Decimal("10.00")
    assert provider_credit == Decimal("90.00")
