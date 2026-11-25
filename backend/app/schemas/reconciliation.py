from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


ReconciliationStatus = Literal[
    "MATCHED",
    "MISMATCHED",
    "MISSING_GATEWAY",
    "MISSING_LOCAL",
]


class GatewayStatementTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_code: Optional[str] = Field(None, min_length=1, max_length=100)
    provider_txn_id: Optional[str] = Field(None, min_length=1, max_length=150)
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    status: Literal[
        "PAID",
        "SUCCESS",
        "PENDING",
        "PROCESSING",
        "FAILED",
        "CANCELLED",
        "CANCELED",
        "EXPIRED",
        "REFUNDED",
    ]
    occurred_at: datetime

    @model_validator(mode="after")
    def require_match_key(self):
        if not self.transaction_code and not self.provider_txn_id:
            raise ValueError("Cần transaction_code hoặc provider_txn_id để đối soát.")
        return self


class GatewayReconciliationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(..., min_length=1, max_length=50)
    gateway_transactions: list[GatewayStatementTransaction] = Field(
        ..., max_length=2000
    )

    @model_validator(mode="after")
    def reject_duplicate_gateway_ids(self):
        transaction_codes = [
            item.transaction_code
            for item in self.gateway_transactions
            if item.transaction_code
        ]
        provider_txn_ids = [
            item.provider_txn_id
            for item in self.gateway_transactions
            if item.provider_txn_id
        ]
        if len(transaction_codes) != len(set(transaction_codes)):
            raise ValueError("Sao kê có transaction_code bị trùng.")
        if len(provider_txn_ids) != len(set(provider_txn_ids)):
            raise ValueError("Sao kê có provider_txn_id bị trùng.")
        return self


class ReconciliationItem(BaseModel):
    reconciliation_status: ReconciliationStatus
    transaction_code: Optional[str] = None
    gateway_transaction_code: Optional[str] = None
    provider_txn_id: Optional[str] = None
    booking_id: Optional[int] = None
    local_amount: Optional[Decimal] = None
    gateway_amount: Optional[Decimal] = None
    difference_amount: Decimal
    local_status: Optional[str] = None
    gateway_status: Optional[str] = None
    refund_status: Optional[str] = None
    refund_amount: Decimal = Decimal("0.00")
    pending_refund_amount: Decimal = Decimal("0.00")
    completed_refund_amount: Decimal = Decimal("0.00")
    anomaly_types: list[str] = Field(default_factory=list)


class ReconciliationSummary(BaseModel):
    total_count: int
    matched_count: int
    mismatched_count: int
    missing_gateway_count: int
    missing_local_count: int
    local_amount_total: Decimal
    gateway_amount_total: Decimal
    difference_amount_total: Decimal
    anomaly_count: int
    pending_refund_count: int
    pending_refund_amount: Decimal
    completed_refund_amount: Decimal


class PaymentReconciliationResponse(BaseModel):
    provider: str
    from_date: date
    to_date: date
    summary: ReconciliationSummary
    transactions: list[ReconciliationItem]


class ReportPeriod(BaseModel):
    from_date: date
    to_date: date


class PaymentPlatformReport(BaseModel):
    transaction_count: int
    transactions_by_status: dict[str, int]
    captured_count: int
    captured_amount: Decimal
    completed_refund_amount: Decimal
    net_collected_amount: Decimal


class RefundPlatformReport(BaseModel):
    refund_count: int
    refunds_by_status: dict[str, int]
    pending_count: int
    pending_amount: Decimal
    completed_count: int
    completed_amount: Decimal


class BookingPlatformReport(BaseModel):
    booking_count: int
    bookings_by_status: dict[str, int]


class PlatformEntityReport(BaseModel):
    user_count: int
    active_user_count: int
    new_user_count: int
    users_by_status: dict[str, int]
    vehicle_count: int
    active_vehicle_count: int
    vehicles_by_status: dict[str, int]


class PlatformAnomalyReport(BaseModel):
    amount_mismatch_count: int
    late_payment_count: int
    pending_refund_count: int
    invalid_signature_webhook_count: int
    failed_webhook_count: int


class PlatformReportResponse(BaseModel):
    period: ReportPeriod
    currency: Literal["VND"] = "VND"
    payments: PaymentPlatformReport
    refunds: RefundPlatformReport
    bookings: BookingPlatformReport
    extra_fee_count: int
    extra_fee_amount: Decimal
    platform: PlatformEntityReport
    anomalies: PlatformAnomalyReport
