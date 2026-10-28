from dataclasses import FrozenInstanceError, replace

import pytest

from bounded_media_worker import WorkerLimits, WorkerPolicy


def test_limits_reject_nonpositive_values() -> None:
    with pytest.raises(ValueError):
        WorkerLimits(max_pages=0)


def test_limits_reject_non_integer_resource_values() -> None:
    with pytest.raises(ValueError):
        WorkerLimits(max_pages=1.5)  # type: ignore[arg-type]


def test_policy_rejects_limit_over_its_application_ceiling() -> None:
    ceiling = WorkerLimits(max_pages=1)
    with pytest.raises(ValueError):
        WorkerPolicy(limits=WorkerLimits(max_pages=2), application_ceiling=ceiling)


def test_policy_is_immutable() -> None:
    policy = WorkerPolicy()
    with pytest.raises(FrozenInstanceError):
        policy.limits = replace(policy.limits, max_pages=1)  # type: ignore[misc]
