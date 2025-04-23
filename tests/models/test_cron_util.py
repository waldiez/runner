# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Tests for waldiez_runner.models.cron_util module."""

import pytest

from waldiez_runner.models.cron_util import (
    CronValidationError,
    normalize_and_validate_cron_expression,
)


def test_standard_cron() -> None:
    """Test standard cron expressions."""
    assert (
        normalize_and_validate_cron_expression("*/5 * * * *") == "*/5 * * * *"
    )
    assert normalize_and_validate_cron_expression("0 0 * * *") == "0 0 * * *"


def test_named_weekday() -> None:
    """Test named weekday cron expressions."""
    assert normalize_and_validate_cron_expression("every monday") == "0 0 * * 1"
    assert normalize_and_validate_cron_expression("every sunday") == "0 0 * * 0"


def test_month_day_expression() -> None:
    """Test month day cron expressions."""
    assert (
        normalize_and_validate_cron_expression("every 15 of january")
        == "0 0 15 1 *"
    )
    assert (
        normalize_and_validate_cron_expression("every 1 of december")
        == "0 0 1 12 *"
    )


def test_natural_intervals() -> None:
    """Test natural interval cron expressions."""
    assert (
        normalize_and_validate_cron_expression("every 5 minutes")
        == "*/5 * * * *"
    )
    assert (
        normalize_and_validate_cron_expression("every 1 hour") == "0 */1 * * *"
    )
    assert (
        normalize_and_validate_cron_expression("every 2 hours") == "0 */2 * * *"
    )
    assert (
        normalize_and_validate_cron_expression("every 3 days") == "0 0 */3 * *"
    )
    assert (
        normalize_and_validate_cron_expression("every 2 weeks")
        == "0 0 */14 * *"
    )
    assert (
        normalize_and_validate_cron_expression("every 6 months")
        == "0 0 1 */6 *"
    )
    assert (
        normalize_and_validate_cron_expression("every 1 week") == "0 0 */7 * *"
    )
    assert (
        normalize_and_validate_cron_expression("every month") == "0 0 1 */1 *"
    )


def test_invalid_cron_syntax() -> None:
    """Test invalid cron expressions."""
    with pytest.raises(CronValidationError):
        normalize_and_validate_cron_expression("this is not cron")

    with pytest.raises(CronValidationError):
        normalize_and_validate_cron_expression("* * *")

    with pytest.raises(CronValidationError):
        normalize_and_validate_cron_expression("every 100 minutes")

    with pytest.raises(CronValidationError):
        normalize_and_validate_cron_expression("every 40 days")

    with pytest.raises(CronValidationError):
        normalize_and_validate_cron_expression("every 0 weeks")

    with pytest.raises(CronValidationError):
        normalize_and_validate_cron_expression("every 33 of february")
