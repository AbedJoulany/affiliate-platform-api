from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_SCHEDULE_LOOKAHEAD_DAYS = 366


class SchedulingError(ValueError):
    """Raised when a policy cannot produce a safe future schedule."""


@dataclass(frozen=True, slots=True)
class ScheduleSlot:
    scheduled_at: datetime
    local_date: date


def resolve_timezone(timezone_name: str | None) -> ZoneInfo:
    candidate = timezone_name or "UTC"
    try:
        return ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise SchedulingError("Workspace timezone is invalid") from exc


def _valid_local_time(local_value: datetime, timezone: ZoneInfo, fold: int) -> datetime | None:
    aware = local_value.replace(tzinfo=timezone, fold=fold)
    round_tripped = aware.astimezone(UTC).astimezone(timezone)
    if round_tripped.replace(tzinfo=None) != local_value:
        return None
    return aware


def resolve_local_time(local_value: datetime, timezone: ZoneInfo) -> datetime:
    """Resolve a wall-clock time deterministically across DST transitions.

    Ambiguous fall-back times use the earlier occurrence (fold=0). A nonexistent
    spring-forward time is moved forward to the first valid wall-clock minute.
    """
    first = _valid_local_time(local_value, timezone, 0)
    if first is not None:
        return first
    second = _valid_local_time(local_value, timezone, 1)
    if second is not None:
        return second
    for minutes in range(1, 181):
        shifted = local_value + timedelta(minutes=minutes)
        first = _valid_local_time(shifted, timezone, 0)
        if first is not None:
            return first
        second = _valid_local_time(shifted, timezone, 1)
        if second is not None:
            return second
    raise SchedulingError("Preferred local time cannot be resolved")


def candidate_schedule_slots(
    *,
    now_utc: datetime,
    timezone_name: str | None,
    preferred_time_local: time,
    posts_per_day: int,
) -> list[ScheduleSlot]:
    """Return deterministic future candidates for the bounded look-ahead window."""
    if now_utc.tzinfo is None:
        raise SchedulingError("Scheduling timestamp must include timezone information")
    if posts_per_day < 1:
        raise SchedulingError("posts_per_day must be positive")

    timezone = resolve_timezone(timezone_name)
    now_utc = now_utc.astimezone(UTC)
    local_today = now_utc.astimezone(timezone).date()
    candidates: list[ScheduleSlot] = []
    for day_offset in range(MAX_SCHEDULE_LOOKAHEAD_DAYS):
        local_day = local_today + timedelta(days=day_offset)
        for index in range(posts_per_day):
            minute_offset = round(index * 24 * 60 / posts_per_day)
            local_value = datetime.combine(local_day, preferred_time_local) + timedelta(
                minutes=minute_offset
            )
            aware = resolve_local_time(local_value, timezone)
            candidate_utc = aware.astimezone(UTC)
            if candidate_utc <= now_utc:
                continue
            candidates.append(
                ScheduleSlot(
                    scheduled_at=candidate_utc,
                    local_date=aware.date(),
                )
            )
    candidates.sort(key=lambda slot: slot.scheduled_at)
    return candidates


def select_schedule_slots(
    *,
    candidates: list[ScheduleSlot],
    existing_timestamps: list[datetime],
    timezone_name: str | None,
    daily_limit: int,
    count: int,
) -> list[ScheduleSlot]:
    """Select slots without exceeding the workspace-local daily limit."""
    if daily_limit < 1:
        raise SchedulingError("posts_per_day must be positive")
    if count < 0:
        raise SchedulingError("Requested schedule count cannot be negative")

    occupied = {_as_utc(timestamp) for timestamp in existing_timestamps}
    by_day: Counter[date] = Counter()
    timezone = resolve_timezone(timezone_name)
    for timestamp in existing_timestamps:
        by_day[_as_utc(timestamp).astimezone(timezone).date()] += 1

    selected: list[ScheduleSlot] = []
    for slot in candidates:
        if len(selected) >= count:
            break
        if slot.scheduled_at in occupied:
            continue
        if by_day[slot.local_date] >= daily_limit:
            continue
        selected.append(slot)
        occupied.add(slot.scheduled_at)
        by_day[slot.local_date] += 1
    if len(selected) != count:
        raise SchedulingError("No available scheduling slot within the look-ahead window")
    return selected


def local_date_for(timestamp: datetime, timezone_name: str | None) -> date:
    return _as_utc(timestamp).astimezone(resolve_timezone(timezone_name)).date()


def _as_utc(timestamp: datetime) -> datetime:
    """Treat naive database timestamps as UTC for SQLite/test compatibility."""
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)
