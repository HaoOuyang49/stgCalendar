"""Official-publication-first solar terms and civil-clock conversion."""

from .api import calendar_at, coverage, get_term, terms_for_year
from .calendar import (EstimatedTermConsentRequired, TermPrecisionConsentRequired,
                       day_hour_pillars, local_clock, year_month_pillars)
from .provenance import ResultConfirmationRequired
from .windows import resolve_windows, resolve_windows_report

__version__ = "0.1.0"
__all__ = ["calendar_at", "coverage", "get_term", "terms_for_year", "local_clock",
           "day_hour_pillars", "year_month_pillars", "resolve_windows", "resolve_windows_report",
           "ResultConfirmationRequired", "EstimatedTermConsentRequired", "TermPrecisionConsentRequired"]
