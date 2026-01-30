import logging

logger = logging.getLogger(__name__)


def _get_ride_score(period):
    """Extract ride_score from a Period object or dict."""
    if hasattr(period, 'ride_score'):
        score = period.ride_score
    elif isinstance(period, dict):
        score = period.get('ride_score')
    else:
        return None

    if score is None or score == "":
        return None

    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def _get_start_time(period):
    """Extract start_time from a Period object or dict."""
    if hasattr(period, 'start_time'):
        return period.start_time
    elif isinstance(period, dict):
        return period.get('startTime', '')
    return ''


def scan_break(periods, arrival_index):
    """
    Scan periods after the arrival time to find if waiting improves ride quality.

    For waypoints with a set ETA. Checks the next 1-4 hours after arrival and
    suggests taking a break if any later hour improves ride_score by more than
    25 points.

    Args:
        periods: List of Period objects with ride_score attribute.
        arrival_index: Index of the period matching the ETA.

    Returns:
        Optimization suggestion dict or None.
    """
    if arrival_index is None or arrival_index < 0:
        return None

    if arrival_index >= len(periods):
        return None

    arrival_period = periods[arrival_index]
    arrival_score = _get_ride_score(arrival_period)

    if arrival_score is None:
        return None

    best_improvement = 0
    best_period = None
    best_offset = 0

    scan_end = min(arrival_index + 5, len(periods))

    for i in range(arrival_index + 1, scan_end):
        score = _get_ride_score(periods[i])

        if score is None:
            continue

        improvement = score - arrival_score
        if improvement > best_improvement:
            best_improvement = improvement
            best_period = periods[i]
            best_offset = i - arrival_index

    if best_improvement > 25:
        optimized_score = _get_ride_score(best_period)
        optimized_start_time = _get_start_time(best_period)

        return {
            "type": "break",
            "message": (
                f"Waiting {best_offset} hour{'s' if best_offset > 1 else ''} "
                f"improves ride quality from {arrival_score} to {optimized_score}. "
                f"Consider taking a break!"
            ),
            "arrival_score": arrival_score,
            "optimized_score": optimized_score,
            "wait_hours": best_offset,
            "optimized_start_time": optimized_start_time,
        }

    return None


def scan_departure_window(all_waypoint_periods, hours_to_scan=12):
    """
    Find the best departure time by simulating different start times.

    For each possible departure hour, simulate the trip where each subsequent
    waypoint is reached 1 hour after the previous one. Average the ride scores
    across all waypoints for each scenario.

    Args:
        all_waypoint_periods: List of period lists, one per waypoint.
                              Each inner list is the full hourly forecast periods.
        hours_to_scan: Number of departure hours to consider (default 12).

    Returns:
        Departure plan dict or None.
    """
    if not all_waypoint_periods:
        return None

    num_waypoints = len(all_waypoint_periods)

    min_periods = min(len(wp) for wp in all_waypoint_periods)
    if min_periods == 0:
        return None

    # Limit scan to what we have data for:
    # Starting at hour H, we need periods at H, H+1, ..., H+(N-1)
    max_start = min(hours_to_scan, min_periods - num_waypoints + 1)
    if max_start <= 0:
        return None

    scenarios = []

    for start_hour in range(max_start):
        scores = []
        valid = True

        for waypoint_idx, waypoint_periods in enumerate(all_waypoint_periods):
            period_idx = start_hour + waypoint_idx

            if period_idx >= len(waypoint_periods):
                valid = False
                break

            score = _get_ride_score(waypoint_periods[period_idx])
            if score is None:
                valid = False
                break

            scores.append(score)

        if valid and scores:
            avg_score = round(sum(scores) / len(scores), 1)
            departure_time = _get_start_time(all_waypoint_periods[0][start_hour])
            scenarios.append({
                "start_hour": start_hour,
                "average_score": avg_score,
                "departure_time": departure_time,
            })

    if not scenarios:
        return None

    # Find best scenario (highest average score)
    best = max(scenarios, key=lambda s: s["average_score"])

    # "Leaving now" is scenario at start_hour 0
    now_scenario = next((s for s in scenarios if s["start_hour"] == 0), None)
    if now_scenario is None:
        return None

    improvement = round(best["average_score"] - now_scenario["average_score"], 1)

    return {
        "golden_window": {
            "departure_time": best["departure_time"],
            "average_score": best["average_score"],
        },
        "improvement": improvement,
    }

def find_arrival_index(periods, eta) -> int | None:
    """Locate the period index whose time window contains the given ETA."""
    for i, period in enumerate(periods):
        try:
            start_dt = datetime.fromisoformat(period.start_time).astimezone(timezone.utc)
            end_dt = datetime.fromisoformat(period.end_time).astimezone(timezone.utc)
            if start_dt <= eta <= end_dt:
                return i
        except (ValueError, TypeError):
            continue
    return None
