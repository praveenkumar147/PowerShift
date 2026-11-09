"""All ORM models. Importing this package registers every table on Base.metadata."""

from powershift.db.models.household import Household
from powershift.db.models.settings import AppSettings

__all__ = ["AppSettings", "Household"]
