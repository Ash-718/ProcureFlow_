"""Founder groups.

Rotation and shell detection have to resolve at the level of people, not
companies.  A founder who has just taken two consecutive awards can incorporate
a fresh entity tomorrow; if the platform counted companies, that would reset the
counter and the rule would mean nothing.

A founder group is therefore the transitive set of companies connected by shared
founders: start from one company, take its founders, take every company those
founders are on, take those companies' founders, and repeat until nothing new
appears.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, CompanyFounder, Founder


@dataclass(frozen=True)
class FounderGroup:
    """Companies and founders that resolve to the same group of people."""

    company_ids: set[int]
    founder_ids: set[int]
    founder_names: list[str]
    company_names: list[str]

    def as_dict(self) -> dict:
        return {
            "company_ids": sorted(self.company_ids),
            "founder_ids": sorted(self.founder_ids),
            "founders": self.founder_names,
            "companies": self.company_names,
        }


def founder_ids_of(db: Session, company_ids: set[int]) -> set[int]:
    if not company_ids:
        return set()
    rows = db.scalars(
        select(CompanyFounder.founder_id).where(CompanyFounder.company_id.in_(company_ids))
    ).all()
    return set(rows)


def company_ids_of(db: Session, founder_ids: set[int]) -> set[int]:
    if not founder_ids:
        return set()
    rows = db.scalars(
        select(CompanyFounder.company_id).where(CompanyFounder.founder_id.in_(founder_ids))
    ).all()
    return set(rows)


def resolve(db: Session, company_id: int) -> FounderGroup:
    """The founder group a company belongs to, closed over shared founders."""

    company_ids = {company_id}
    founder_ids: set[int] = set()

    while True:
        new_founders = founder_ids_of(db, company_ids) - founder_ids
        founder_ids |= new_founders
        new_companies = company_ids_of(db, founder_ids) - company_ids
        company_ids |= new_companies
        if not new_founders and not new_companies:
            break

    founder_names = sorted(
        db.scalars(select(Founder.name).where(Founder.id.in_(founder_ids))).all()
    ) if founder_ids else []
    company_names = sorted(
        db.scalars(select(Company.name).where(Company.id.in_(company_ids))).all()
    )

    return FounderGroup(
        company_ids=company_ids,
        founder_ids=founder_ids,
        founder_names=founder_names,
        company_names=company_names,
    )
