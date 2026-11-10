"""All ORM models. Importing this package registers every table on Base.metadata."""

from powershift.db.models.appliance import (
    Appliance,
    ApplianceFlexConstraint,
    ApplianceOperatingDay,
    ApplianceUsageBlock,
)
from powershift.db.models.household import Household
from powershift.db.models.optimization import OptimizationRun, OptimizationRunItem
from powershift.db.models.settings import AppSettings
from powershift.db.models.tariff import Tariff, TariffCharge, TariffPeriod, TariffSlab

__all__ = [
    "AppSettings",
    "Appliance",
    "ApplianceFlexConstraint",
    "ApplianceOperatingDay",
    "ApplianceUsageBlock",
    "Household",
    "OptimizationRun",
    "OptimizationRunItem",
    "Tariff",
    "TariffCharge",
    "TariffPeriod",
    "TariffSlab",
]
