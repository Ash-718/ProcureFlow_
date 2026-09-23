"""The rules service - the only way any engine learns a number.

Non-negotiable rule 1: no threshold, percentage or limit is hard-coded anywhere.
Every one lives in procurement_rule and is read through this service.

If a rule is missing the service raises.  It never substitutes a default,
because a silent default is a hard-coded threshold wearing a disguise.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import RuleType
from app.models import ProcurementRule


class RuleNotFound(LookupError):
    """Raised when an engine asks for a rule that is not active in the table."""

    def __init__(self, rule_name: str) -> None:
        super().__init__(
            f"No active procurement rule named {rule_name}. "
            f"Engines never fall back to a built-in default - add the rule instead."
        )
        self.rule_name = rule_name


@dataclass(frozen=True)
class RuleValue:
    """A rule as an engine sees it, carrying everything needed to explain it."""

    rule_name: str
    rule_type: RuleType
    value: Decimal
    source_reference: str | None
    effective_from: date
    description: str | None

    @property
    def is_prototype_setting(self) -> bool:
        """True when the rule has no source reference.

        A prototype setting is a working assumption, not a verified legal
        requirement, and the UI labels it as such.
        """
        return not self.source_reference

    def cite(self) -> str:
        """How this rule is named inside a human-readable explanation."""
        label = f"{self.rule_name} = {self.value:f}"
        if self.is_prototype_setting:
            return f"{label} (prototype setting, no source reference)"
        return f"{label} (source: {self.source_reference})"


class RulesService:
    """Reads procurement rules, and remembers which ones it was asked for.

    The record of what was read is what lets a decision cite its own basis.
    """

    def __init__(self, db: Session, as_of: date | None = None) -> None:
        self.db = db
        self.as_of = as_of or date.today()
        self._read: dict[str, RuleValue] = {}

    def get(self, rule_name: str) -> RuleValue:
        row = self.db.scalars(
            select(ProcurementRule)
            .where(
                ProcurementRule.rule_name == rule_name,
                ProcurementRule.active.is_(True),
                ProcurementRule.effective_from <= self.as_of,
            )
            # The most recently effective version of the rule wins.
            .order_by(ProcurementRule.effective_from.desc(), ProcurementRule.id.desc())
        ).first()

        if row is None:
            raise RuleNotFound(rule_name)

        rule = RuleValue(
            rule_name=row.rule_name,
            rule_type=row.rule_type,
            value=row.value,
            source_reference=row.source_reference,
            effective_from=row.effective_from,
            description=row.description,
        )
        self._read[rule.rule_name] = rule
        return rule

    def decimal(self, rule_name: str) -> Decimal:
        return self.get(rule_name).value

    def integer(self, rule_name: str) -> int:
        return int(self.get(rule_name).value)

    @property
    def rules_read(self) -> list[RuleValue]:
        """Every rule this service was asked for, in name order."""
        return [self._read[name] for name in sorted(self._read)]

    def citations(self) -> list[str]:
        return [rule.cite() for rule in self.rules_read]
