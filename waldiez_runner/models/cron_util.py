# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=line-too-long
# flake8: noqa: E501

"""Simple cron expression validator and normalizer."""

import re


class CronValidationError(ValueError):
    """Custom exception for cron expression validation errors."""


def normalize_and_validate_cron_expression(expr: str) -> str:
    """
    Validate and normalize a cron expression.

    Validates a cron expression or a natural interval string,
    and returns a normalized 5-field cron string.

    Supports:
        - Standard 5-field cron expressions
        - "every X minutes/hours/days/weeks/months"
        - "every monday", "every tuesday", ...
        - "every 15 of january", ...

    Parameters
    ----------
    expr : str
        The cron expression or natural interval string to validate.
        It can be a standard cron expression or a natural interval string.

    Returns
    -------
    str
        The normalized cron expression in the standard 5-field format.

    Raises
    ------
    CronValidationError
        If the cron expression is invalid or cannot be normalized.
    """
    expr = expr.strip().lower()

    # === Named weekday ===
    if match := re.fullmatch(
        r"every (monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
        expr,
    ):
        day_map = {
            "sunday": 0,
            "monday": 1,
            "tuesday": 2,
            "wednesday": 3,
            "thursday": 4,
            "friday": 5,
            "saturday": 6,
        }
        weekday = match.group(1)
        return f"0 0 * * {day_map[weekday]}"

    # === Interval: every X units ===
    if match := re.fullmatch(
        r"every (\d{1,2}) of (january|february|march|april|may|june|july|august|september|october|november|december)",
        expr,
    ):
        day, month = match.groups()
        month_map = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
        }
        day_int = int(day)
        if not 1 <= day_int <= 31:
            raise CronValidationError("Day must be between 1 and 31")
        return f"0 0 {day_int} {month_map[month]} *"

    # === Interval: every X units ===
    if match := re.fullmatch(
        r"every(?: (\d+|one))? (minute|minutes|hour|hours|day|days|week|weeks|month|months)",
        expr,
    ):
        value_str, unit = match.groups()
        value = 1 if value_str in (None, "one") else int(value_str)
        return normalize_natural_interval(value, unit)

    # === Standard 5-field cron ===
    parts = expr.split()
    if len(parts) != 5:
        raise CronValidationError("Cron expression must have exactly 5 fields")

    cron_part_pattern = re.compile(r"^(\*|\*/?\d+|\d+(-\d+)?)(,\d+(-\d+)?)*$")
    for part in parts:
        if not cron_part_pattern.match(part):
            raise CronValidationError(f"Invalid cron field: {part}")

    return expr


# pylint: disable=too-complex
def normalize_natural_interval(value: int, unit: str) -> str:
    """Normalize a natural interval string to a cron expression.

    Parameters
    ----------
    value : int
        The numeric value of the interval.
    unit : str
        The unit of the interval (e.g., "minute", "hour", "day", etc.).

    Returns
    -------
    str
        The normalized cron expression in the standard 5-field format.

    Raises
    ------
    CronValidationError
        If the value or unit is invalid.

    """
    if unit.startswith("minute"):
        if value < 1 or value > 59:
            raise CronValidationError("Minutes must be between 1 and 59")
        return f"*/{value} * * * *"

    if unit.startswith("hour"):
        if value < 1 or value > 23:
            raise CronValidationError("Hours must be between 1 and 23")
        return f"0 */{value} * * *"

    if unit.startswith("day"):
        if value < 1 or value > 31:
            raise CronValidationError("Days must be between 1 and 31")
        return f"0 0 */{value} * *"

    if unit.startswith("week"):
        if value < 1 or value > 52:
            raise CronValidationError("Weeks must be between 1 and 52")
        days = value * 7
        return f"0 0 */{days} * *"  # Approximate: every N*7 days

    if unit.startswith("month"):
        if value < 1 or value > 12:
            raise CronValidationError("Months must be between 1 and 12")
        return f"0 0 1 */{value} *"

    raise CronValidationError(f"Unsupported unit: {unit}")
