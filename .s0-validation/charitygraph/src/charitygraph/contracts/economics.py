"""Pooled cohort, pricing, FX and cost-ledger contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from .common import ArtifactRecord, ArtifactRef, CanonicalObject, SchemaRef, Sha256, StrictModel, VersionedPolicy, utc_datetime, require_nonblank
from .ids import validate_typed_id
from .tasks import PaidOutputCategory, ProviderUsage


def _schema(name: str) -> SchemaRef:
    return SchemaRef(schema_id=f"urn:charitygraph:builder:schema:{name}:1.0", schema_version="1.0")


def _prefix(value: str, prefix: str, field_name: str) -> str:
    try:
        return validate_typed_id(value, prefix)  # type: ignore[arg-type]
    except ValueError as exc:
        raise ValueError(f"{field_name} must use {prefix} typed ID") from exc


def _url_without_query(value: str, field_name: str) -> str:
    require_nonblank(value, field_name)
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError(f"{field_name} must be an absolute URL without query or fragment")
    return value


class Money(StrictModel):
    amount: Decimal
    currency: str

    @field_validator("amount", mode="before")
    @classmethod
    def _decimal(cls, value):
        if isinstance(value, float):
            raise TypeError("Money cannot use binary float")
        return value

    @field_validator("amount")
    @classmethod
    def _nonnegative(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0:
            raise ValueError("money amounts must be finite and non-negative")
        return value

    @field_validator("currency")
    @classmethod
    def _currency(cls, value: str) -> str:
        if len(value) != 3 or not value.isascii() or not value.isupper() or not value.isalpha():
            raise ValueError("currency must be three upper-case ASCII letters")
        return value


class SignedMoney(StrictModel):
    """A finite signed amount used only for reconciled totals, never input charges."""

    amount: Decimal
    currency: str

    @field_validator("amount", mode="before")
    @classmethod
    def _decimal(cls, value):
        if isinstance(value, float):
            raise TypeError("SignedMoney cannot use binary float")
        return value

    @field_validator("amount")
    @classmethod
    def _finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("signed money amounts must be finite")
        return value

    @field_validator("currency")
    @classmethod
    def _currency(cls, value: str) -> str:
        if len(value) != 3 or not value.isascii() or not value.isupper() or not value.isalpha():
            raise ValueError("currency must be three upper-case ASCII letters")
        return value

class BudgetCohort(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("budget-cohort"), validation_alias="schema", serialization_alias="schema")
    cohort_code: Literal["C100", "C1K", "C10K", "SPIKE"]
    definition_version: str
    ranking_metric: Literal["donor_decision_exposure_proxy"]
    rank_start: int
    rank_end: int
    expected_member_count: int
    membership_manifest_ref: str
    membership_hash: Sha256
    fallback_proxy_policy_id: str | None = None
    budget_cap: Money
    pooling: Literal["within_cohort_only"]
    created_at: datetime

    @field_validator("record_id")
    @classmethod
    def _record(cls, value: str) -> str:
        return _prefix(value, "cohort:", "record_id")

    @field_validator("definition_version", "membership_manifest_ref")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("rank_start", "rank_end", "expected_member_count")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("cohort rank/count values must be positive")
        return value

    _created_at = field_validator("created_at")(utc_datetime)

    @model_validator(mode="after")
    def _cohort_rules(self) -> "BudgetCohort":
        if self.rank_end < self.rank_start:
            raise ValueError("rank_end must not precede rank_start")
        if self.cohort_code == "C100" and (self.rank_start, self.rank_end, self.expected_member_count) != (1, 100, 100):
            raise ValueError("C100 must cover ranks 1-100 and 100 subjects")
        if self.cohort_code == "C1K" and (self.rank_start, self.rank_end, self.expected_member_count) != (101, 1100, 1000):
            raise ValueError("C1K must cover ranks 101-1100 and 1000 subjects")
        if self.cohort_code == "C10K" and (self.rank_start, self.rank_end, self.expected_member_count) != (1101, 11100, 10000):
            raise ValueError("C10K must cover ranks 1101-11100 and 10000 subjects")
        if self.cohort_code != "SPIKE" and (self.budget_cap.currency != "AUD" or self.budget_cap.amount != Decimal("100")):
            raise ValueError("production cohorts have an AUD 100 pooled cap")
        if self.cohort_code == "SPIKE" and self.budget_cap.amount <= 0:
            raise ValueError("SPIKE requires a positive separately approved cap")
        return self


class PriceRate(StrictModel):
    dimension: Literal["input_tokens", "cached_input_tokens", "output_tokens", "embedding_input_tokens", "image_units", "tool_calls", "other"]
    unit_quantity: Decimal
    price_per_unit: Decimal
    other_dimension_name: str | None = None

    @field_validator("unit_quantity", "price_per_unit", mode="before")
    @classmethod
    def _no_float(cls, value):
        if isinstance(value, float):
            raise TypeError("pricing rates cannot use binary float")
        return value

    @field_validator("unit_quantity")
    @classmethod
    def _quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError("unit_quantity must be positive and finite")
        return value

    @field_validator("price_per_unit")
    @classmethod
    def _price(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0:
            raise ValueError("price_per_unit must be finite and non-negative")
        return value

    @model_validator(mode="after")
    def _other_name(self) -> "PriceRate":
        if self.dimension == "other" and not self.other_dimension_name:
            raise ValueError("other pricing dimensions require a name")
        if self.dimension != "other" and self.other_dimension_name is not None:
            raise ValueError("named dimensions cannot carry other_dimension_name")
        return self


class PricingSnapshot(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("pricing-snapshot"), validation_alias="schema", serialization_alias="schema")
    provider_id: str
    model_snapshot: str
    effective_at: datetime
    retrieved_at: datetime
    provider_currency: str
    authoritative_source_url: str
    rates: tuple[PriceRate, ...]
    source_content_hash: Sha256

    @field_validator("record_id")
    @classmethod
    def _record(cls, value: str) -> str:
        return _prefix(value, "pricing:", "record_id")

    @field_validator("provider_id", "model_snapshot", "provider_currency")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("effective_at", "retrieved_at")
    @classmethod
    def _times(cls, value: datetime) -> datetime:
        return utc_datetime(value)

    @field_validator("authoritative_source_url")
    @classmethod
    def _url(cls, value: str) -> str:
        return _url_without_query(value, "authoritative_source_url")

    @field_validator("rates")
    @classmethod
    def _rates(cls, value: tuple[PriceRate, ...]) -> tuple[PriceRate, ...]:
        if not value or len({(item.dimension, item.other_dimension_name) for item in value}) != len(value):
            raise ValueError("pricing dimensions must be present and unique")
        return value


class FxRateSnapshot(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("fx-rate-snapshot"), validation_alias="schema", serialization_alias="schema")
    base_currency: str
    quote_currency: Literal["AUD"]
    aud_per_base_unit: Decimal
    observed_at: datetime
    source_name: str
    source_url: str
    source_content_hash: Sha256

    @field_validator("record_id")
    @classmethod
    def _record(cls, value: str) -> str:
        return _prefix(value, "fx:", "record_id")

    @field_validator("base_currency")
    @classmethod
    def _base(cls, value: str) -> str:
        if len(value) != 3 or not value.isascii() or not value.isupper() or not value.isalpha():
            raise ValueError("base_currency must be three upper-case ASCII letters")
        return value

    @field_validator("aud_per_base_unit", mode="before")
    @classmethod
    def _no_float(cls, value):
        if isinstance(value, float):
            raise TypeError("FX rates cannot use binary float")
        return value

    @field_validator("aud_per_base_unit")
    @classmethod
    def _rate(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError("FX rate must be positive and finite")
        return value

    _observed_at = field_validator("observed_at")(utc_datetime)

    @field_validator("source_name")
    @classmethod
    def _source(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("source_url")
    @classmethod
    def _url(cls, value: str) -> str:
        return _url_without_query(value, "source_url")


class CostReservation(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("cost-reservation"), validation_alias="schema", serialization_alias="schema")
    cohort_id: str
    run_id: str
    model_task_ids: tuple[str, ...]
    pricing_snapshot_id: str
    fx_snapshot_id: str
    estimated_provider_cost: Money
    reserved_aud: Money
    paid_output_categories: tuple[PaidOutputCategory, ...]
    reserved_at: datetime
    expires_at: datetime | None = None

    @field_validator("record_id")
    @classmethod
    def _record(cls, value: str) -> str:
        return _prefix(value, "reservation:", "record_id")

    @field_validator("cohort_id", "run_id", "pricing_snapshot_id", "fx_snapshot_id")
    @classmethod
    def _refs(cls, value: str, info) -> str:
        prefix = {"cohort_id": "cohort:", "run_id": "run:", "pricing_snapshot_id": "pricing:", "fx_snapshot_id": "fx:"}[info.field_name]
        return _prefix(value, prefix, info.field_name)

    @field_validator("model_task_ids")
    @classmethod
    def _tasks(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(set(value)) != len(value):
            raise ValueError("cost reservations require unique model tasks")
        for item in value:
            _prefix(item, "modeltask:", "model_task_id")
        return value

    @field_validator("reserved_aud")
    @classmethod
    def _aud(cls, value: Money) -> Money:
        if value.currency != "AUD":
            raise ValueError("reserved_aud must be AUD")
        return value

    @field_validator("paid_output_categories")
    @classmethod
    def _categories(cls, value: tuple[PaidOutputCategory, ...]) -> tuple[PaidOutputCategory, ...]:
        if not value or len(set(value)) != len(value):
            raise ValueError("reservations require unique paid-output categories")
        return value

    @field_validator("reserved_at", "expires_at")
    @classmethod
    def _times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else utc_datetime(value)


class CostLedgerEntry(StrictModel):
    """One immutable accounting fact; all charge amounts remain non-negative Money."""

    cohort_id: str
    run_id: str
    task_run_id: str
    reservation_id: str
    pricing_snapshot_id: str
    fx_snapshot_id: str
    entry_type: Literal["reservation", "reservation_release", "actual", "credit", "adjustment"]
    paid_output_category: PaidOutputCategory
    provider_cost: Money
    aud_cost: Money
    usage: ProviderUsage
    recorded_at: datetime
    adjustment_direction: Literal["debit", "credit"] | None = None
    provider_invoice_ref: str | None = None

    @field_validator("cohort_id", "run_id", "task_run_id", "reservation_id", "pricing_snapshot_id", "fx_snapshot_id")
    @classmethod
    def _refs(cls, value: str, info) -> str:
        prefix = {"cohort_id": "cohort:", "run_id": "run:", "task_run_id": "taskrun:", "reservation_id": "reservation:", "pricing_snapshot_id": "pricing:", "fx_snapshot_id": "fx:"}[info.field_name]
        return _prefix(value, prefix, info.field_name)

    @field_validator("aud_cost")
    @classmethod
    def _aud(cls, value: Money) -> Money:
        if value.currency != "AUD":
            raise ValueError("aud_cost must be AUD")
        return value

    _recorded_at = field_validator("recorded_at")(utc_datetime)

    @model_validator(mode="after")
    def _adjustment_semantics(self) -> "CostLedgerEntry":
        if self.entry_type == "adjustment" and self.adjustment_direction is None:
            raise ValueError("adjustments require an explicit debit or credit direction")
        if self.entry_type != "adjustment" and self.adjustment_direction is not None:
            raise ValueError("only adjustments may carry adjustment_direction")
        return self


class ReservationReconciliation(StrictModel):
    """Per-reservation accounting position; unmatched actuals are represented separately on CostLedger."""

    reservation_id: str
    reserved_aud: Money
    actual_charge_aud: Money
    actual_consuming_reservation_aud: Money
    released_unused_reserve_aud: Money
    reservation_overrun_aud: Money
    outstanding_reserved_exposure_aud: Money

    @field_validator("reservation_id")
    @classmethod
    def _reservation(cls, value: str) -> str:
        return _prefix(value, "reservation:", "reservation_id")

    @field_validator(
        "reserved_aud", "actual_charge_aud", "actual_consuming_reservation_aud",
        "released_unused_reserve_aud", "reservation_overrun_aud", "outstanding_reserved_exposure_aud",
    )
    @classmethod
    def _aud(cls, value: Money) -> Money:
        if value.currency != "AUD":
            raise ValueError("reservation reconciliation money must be AUD")
        return value

    @model_validator(mode="after")
    def _reconcile_position(self) -> "ReservationReconciliation":
        if self.actual_consuming_reservation_aud.amount + self.reservation_overrun_aud.amount != self.actual_charge_aud.amount:
            raise ValueError("reservation actual charge must equal consumed reserve plus overrun")
        if (
            self.actual_consuming_reservation_aud.amount
            + self.released_unused_reserve_aud.amount
            + self.outstanding_reserved_exposure_aud.amount
            != self.reserved_aud.amount
        ):
            raise ValueError("reservation use, release and outstanding exposure must equal reserved amount")
        return self


class CostLedger(ArtifactRecord):
    """Append-only accounting with exact per-reservation exposure and faithful actual-cost overruns."""

    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("cost-ledger"), validation_alias="schema", serialization_alias="schema")
    cohort_id: str
    budget_cap_aud: Money
    entries: tuple[CostLedgerEntry, ...] = ()
    reservation_reconciliations: tuple[ReservationReconciliation, ...]
    as_at: datetime
    reserved_exposure_aud: Money
    released_reservations_aud: Money
    actual_spend_aud: Money
    reservation_overrun_aud: Money
    unreserved_actual_aud: Money
    credits_aud: Money
    adjustment_debits_aud: Money
    adjustment_credits_aud: Money
    net_actual_spend_aud: SignedMoney
    committed_exposure_aud: SignedMoney
    remaining_budget_aud: SignedMoney
    breach: bool

    @field_validator("record_id")
    @classmethod
    def _record(cls, value: str) -> str:
        return _prefix(value, "costledger:", "record_id")

    @field_validator("cohort_id")
    @classmethod
    def _cohort(cls, value: str) -> str:
        return _prefix(value, "cohort:", "cohort_id")

    @field_validator(
        "budget_cap_aud", "reserved_exposure_aud", "released_reservations_aud", "actual_spend_aud",
        "reservation_overrun_aud", "unreserved_actual_aud", "credits_aud", "adjustment_debits_aud",
        "adjustment_credits_aud",
    )
    @classmethod
    def _aud(cls, value: Money) -> Money:
        if value.currency != "AUD":
            raise ValueError("cost ledger money must be AUD")
        return value

    @field_validator("reservation_reconciliations")
    @classmethod
    def _reservation_ids(cls, value: tuple[ReservationReconciliation, ...]) -> tuple[ReservationReconciliation, ...]:
        if len({item.reservation_id for item in value}) != len(value):
            raise ValueError("reservation reconciliations must be unique by reservation_id")
        return value

    @field_validator("net_actual_spend_aud", "committed_exposure_aud", "remaining_budget_aud")
    @classmethod
    def _signed_aud(cls, value: SignedMoney) -> SignedMoney:
        if value.currency != "AUD":
            raise ValueError("reconciled ledger totals must be AUD")
        return value

    _as_at = field_validator("as_at")(utc_datetime)

    @model_validator(mode="after")
    def _reconcile(self) -> "CostLedger":
        reservation_ids = {item.reservation_id for item in self.entries if item.entry_type == "reservation"}
        release_ids = {item.reservation_id for item in self.entries if item.entry_type == "reservation_release"}
        if not release_ids.issubset(reservation_ids):
            raise ValueError("reservation releases require a matching reservation")
        positions = {item.reservation_id: item for item in self.reservation_reconciliations}
        if set(positions) != reservation_ids:
            raise ValueError("ledger must contain exactly one reconciliation for every reservation")

        def total(entry_type: str, reservation_id: str | None = None) -> Decimal:
            return sum(
                (
                    item.aud_cost.amount for item in self.entries
                    if item.entry_type == entry_type and (reservation_id is None or item.reservation_id == reservation_id)
                ),
                Decimal("0"),
            )

        reservation_overrun = Decimal("0")
        reserved_exposure = Decimal("0")
        for reservation_id in reservation_ids:
            reserved = total("reservation", reservation_id)
            actual = total("actual", reservation_id)
            released = total("reservation_release", reservation_id)
            consumed = min(actual, reserved)
            overrun = max(actual - reserved, Decimal("0"))
            outstanding = reserved - consumed - released
            if outstanding < 0:
                raise ValueError("releases cannot exceed the unused portion of their own reservation")
            position = positions[reservation_id]
            expected_position = (
                (position.reserved_aud.amount, reserved),
                (position.actual_charge_aud.amount, actual),
                (position.actual_consuming_reservation_aud.amount, consumed),
                (position.released_unused_reserve_aud.amount, released),
                (position.reservation_overrun_aud.amount, overrun),
                (position.outstanding_reserved_exposure_aud.amount, outstanding),
            )
            if any(actual_value != expected_value for actual_value, expected_value in expected_position):
                raise ValueError("reservation reconciliation does not match its entry facts")
            reservation_overrun += overrun
            reserved_exposure += outstanding

        releases = total("reservation_release")
        actual = total("actual")
        unreserved_actual = sum(
            (item.aud_cost.amount for item in self.entries if item.entry_type == "actual" and item.reservation_id not in reservation_ids),
            Decimal("0"),
        )
        credits = total("credit")
        adjustment_debits = sum((item.aud_cost.amount for item in self.entries if item.entry_type == "adjustment" and item.adjustment_direction == "debit"), Decimal("0"))
        adjustment_credits = sum((item.aud_cost.amount for item in self.entries if item.entry_type == "adjustment" and item.adjustment_direction == "credit"), Decimal("0"))
        net_actual = actual + adjustment_debits - credits - adjustment_credits
        committed = net_actual + reserved_exposure
        remaining = self.budget_cap_aud.amount - committed
        expected_unsigned = (
            (self.reserved_exposure_aud.amount, reserved_exposure),
            (self.released_reservations_aud.amount, releases),
            (self.actual_spend_aud.amount, actual),
            (self.reservation_overrun_aud.amount, reservation_overrun),
            (self.unreserved_actual_aud.amount, unreserved_actual),
            (self.credits_aud.amount, credits),
            (self.adjustment_debits_aud.amount, adjustment_debits),
            (self.adjustment_credits_aud.amount, adjustment_credits),
        )
        if any(actual_value != expected_value for actual_value, expected_value in expected_unsigned):
            raise ValueError("cost ledger unsigned totals do not reconcile with entries")
        expected_signed = (
            (self.net_actual_spend_aud.amount, net_actual),
            (self.committed_exposure_aud.amount, committed),
            (self.remaining_budget_aud.amount, remaining),
        )
        if any(actual_value != expected_value for actual_value, expected_value in expected_signed):
            raise ValueError("cost ledger signed totals do not reconcile with entries")
        if self.breach != (committed > self.budget_cap_aud.amount):
            raise ValueError("cost ledger breach flag does not match committed exposure")
        return self

class RunManifest(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("run-manifest"), validation_alias="schema", serialization_alias="schema")
    run_kind: Literal["contract_fixture", "economics_spike", "vertical_slice", "cohort_build", "reindex"]
    status: Literal["planned", "running", "completed", "completed_with_failures", "failed", "cancelled"]
    cohort_id: str | None = None
    requested_task_ids: tuple[str, ...] = ()
    input_artifacts: tuple[ArtifactRef, ...] = ()
    pricing_snapshot_ids: tuple[str, ...] = ()
    fx_snapshot_ids: tuple[str, ...] = ()
    policy_refs: tuple[VersionedPolicy, ...] = ()
    configuration_hash: Sha256
    budget_cap_aud: Money | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output_artifact_ids: tuple[str, ...] = ()
    failed_task_ids: tuple[str, ...] = ()

    @field_validator("record_id")
    @classmethod
    def _record(cls, value: str) -> str:
        return _prefix(value, "run:", "record_id")

    @field_validator("cohort_id")
    @classmethod
    def _cohort(cls, value: str | None) -> str | None:
        return None if value is None else _prefix(value, "cohort:", "cohort_id")

    @field_validator("requested_task_ids", "pricing_snapshot_ids", "fx_snapshot_ids", "output_artifact_ids", "failed_task_ids")
    @classmethod
    def _unique_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("RunManifest identifiers must be unique")
        return value

    @field_validator("requested_task_ids", "failed_task_ids")
    @classmethod
    def _task_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            _prefix(item, "modeltask:", "task_id")
        return value

    @field_validator("pricing_snapshot_ids")
    @classmethod
    def _pricing_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            _prefix(item, "pricing:", "pricing_snapshot_id")
        return value

    @field_validator("fx_snapshot_ids")
    @classmethod
    def _fx_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            _prefix(item, "fx:", "fx_snapshot_id")
        return value

    @field_validator("budget_cap_aud")
    @classmethod
    def _aud(cls, value: Money | None) -> Money | None:
        if value is not None and value.currency != "AUD":
            raise ValueError("budget_cap_aud must be AUD")
        return value

    @field_validator("started_at", "completed_at")
    @classmethod
    def _times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else utc_datetime(value)

    @model_validator(mode="after")
    def _status_times(self) -> "RunManifest":
        terminal = {"completed", "completed_with_failures", "failed", "cancelled"}
        if self.status == "planned" and (self.started_at is not None or self.completed_at is not None):
            raise ValueError("planned runs cannot have execution timestamps")
        if self.status == "running" and (self.started_at is None or self.completed_at is not None):
            raise ValueError("running runs require started_at and no completed_at")
        if self.status in terminal and self.completed_at is None:
            raise ValueError("terminal runs require completed_at")
        if self.completed_at is not None and self.started_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        if not set(self.failed_task_ids).issubset(set(self.requested_task_ids)):
            raise ValueError("failed tasks must be requested tasks")
        return self
