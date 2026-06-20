"""Part 10 — Account Health & Service. The whole system rests on the registered owner's
account staying healthy. The Shop Performance Score depends on shipping speed, refund
rate, and service response time, and a low score throttles your reach. One suspension and
the store is gone. This computes a health proxy and flags throttle risk early."""

from .health import (
    SUSPENSION_THRESHOLD,
    THROTTLE_THRESHOLD,
    AccountHealth,
    assess_health,
)

__all__ = ["AccountHealth", "assess_health", "THROTTLE_THRESHOLD", "SUSPENSION_THRESHOLD"]
