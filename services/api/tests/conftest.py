import pytest

from app.services.municipal import _in_memory_work_orders
from app.services.reports import _in_memory_reports, _report_attempts, _report_counts_cache
from app.services.weather import rain_store


@pytest.fixture(autouse=True)
def clean_test_state():
    """Ensure in-memory state does not leak across test modules."""
    _in_memory_reports.clear()
    _report_attempts.clear()
    _report_counts_cache["counts"] = {}
    _report_counts_cache["last_checked"] = 0.0
    _in_memory_work_orders.clear()
    rain_store.set_simulator("none")
    yield
    _in_memory_reports.clear()
    _report_attempts.clear()
    _report_counts_cache["counts"] = {}
    _report_counts_cache["last_checked"] = 0.0
    _in_memory_work_orders.clear()
    rain_store.set_simulator("none")
