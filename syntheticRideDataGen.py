"""
Synthetic Ride Score Training Data Generator

Generates realistic motorcycle riding condition data using 15 weather archetypes
based on US climate patterns (Köppen zones). Features are correlated rather than
independently sampled, and scoring uses research-backed thresholds from:
- Motorcycle Safety Foundation (MSF) wind guidelines
- NWS official wind chill / heat index formulas
- FHWA fog/visibility crash data
- IIHS motorcycle rain crash statistics
- TRO.bike riding condition recommendations

Output: syntheticRideScoreData.csv with columns matching ride_quality.py feature order:
  temp, wind_speed, precip_prob, visibility, humidity, is_day,
  wind_gust, gust_delta, apparent_temp, ride_score
"""

import math
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# NWS Apparent Temperature Formulas
# ---------------------------------------------------------------------------

def wind_chill(temp_f: float, wind_mph: float) -> float:
    """NWS Wind Chill formula. Valid for temp <= 50°F and wind > 3 mph."""
    if temp_f > 50 or wind_mph <= 3:
        return temp_f
    return (
        35.74
        + 0.6215 * temp_f
        - 35.75 * (wind_mph ** 0.16)
        + 0.4275 * temp_f * (wind_mph ** 0.16)
    )


def heat_index(temp_f: float, rh: float) -> float:
    """NWS Heat Index formula. Valid for temp >= 80°F."""
    if temp_f < 80:
        return temp_f
    # Rothfusz regression
    hi = (
        -42.379
        + 2.04901523 * temp_f
        + 10.14333127 * rh
        - 0.22475541 * temp_f * rh
        - 0.00683783 * temp_f ** 2
        - 0.05481717 * rh ** 2
        + 0.00122874 * temp_f ** 2 * rh
        + 0.00085282 * temp_f * rh ** 2
        - 0.00000199 * temp_f ** 2 * rh ** 2
    )
    # Low-humidity adjustment
    if rh < 13 and 80 <= temp_f <= 112:
        hi -= ((13 - rh) / 4) * math.sqrt((17 - abs(temp_f - 95)) / 17)
    # High-humidity adjustment
    if rh > 85 and 80 <= temp_f <= 87:
        hi += ((rh - 85) / 10) * ((87 - temp_f) / 5)
    return hi


def apparent_temperature(temp_f: float, wind_mph: float, rh: float) -> float:
    """Compute apparent temperature using NWS rules."""
    if temp_f <= 50 and wind_mph > 3:
        return wind_chill(temp_f, wind_mph)
    elif temp_f >= 80:
        return heat_index(temp_f, rh)
    else:
        return temp_f


# ---------------------------------------------------------------------------
# Weather Archetypes — 15 realistic US climate scenarios
# ---------------------------------------------------------------------------

ARCHETYPES = [
    {
        "name": "Perfect riding day",
        "temp": (72, 5), "wind": (8, 3), "precip": (5, 5),
        "vis": (10, 0.5), "humid": (45, 10), "day_pct": 0.90, "weight": 0.14,
    },
    {
        "name": "Warm clear day",
        "temp": (82, 5), "wind": (10, 4), "precip": (10, 8),
        "vis": (9.5, 1), "humid": (50, 12), "day_pct": 0.85, "weight": 0.10,
    },
    {
        "name": "Hot humid (SE summer)",
        "temp": (95, 6), "wind": (7, 3), "precip": (25, 15),
        "vis": (8, 1.5), "humid": (78, 8), "day_pct": 0.85, "weight": 0.09,
    },
    {
        "name": "Mild spring",
        "temp": (58, 6), "wind": (10, 4), "precip": (20, 12),
        "vis": (9, 1.5), "humid": (55, 12), "day_pct": 0.80, "weight": 0.12,
    },
    {
        "name": "Cool autumn",
        "temp": (50, 7), "wind": (12, 5), "precip": (15, 10),
        "vis": (9, 1.5), "humid": (50, 12), "day_pct": 0.75, "weight": 0.12,
    },
    {
        "name": "Rainy day",
        "temp": (62, 8), "wind": (15, 6), "precip": (70, 15),
        "vis": (4, 2), "humid": (85, 8), "day_pct": 0.70, "weight": 0.07,
    },
    {
        "name": "Heavy storm",
        "temp": (65, 10), "wind": (30, 8), "precip": (90, 8),
        "vis": (2, 1.5), "humid": (92, 5), "day_pct": 0.60, "weight": 0.02,
    },
    {
        "name": "Windy day (plains)",
        "temp": (68, 8), "wind": (25, 7), "precip": (15, 10),
        "vis": (8, 1.5), "humid": (40, 12), "day_pct": 0.80, "weight": 0.05,
    },
    {
        "name": "Foggy morning",
        "temp": (55, 5), "wind": (4, 2), "precip": (30, 15),
        "vis": (1.5, 1), "humid": (93, 4), "day_pct": 0.40, "weight": 0.06,
    },
    {
        "name": "Cold winter day",
        "temp": (33, 8), "wind": (15, 6), "precip": (20, 15),
        "vis": (7, 2), "humid": (55, 15), "day_pct": 0.65, "weight": 0.02,
    },
    {
        "name": "Freezing/icy",
        "temp": (22, 8), "wind": (12, 5), "precip": (30, 15),
        "vis": (5, 2.5), "humid": (60, 15), "day_pct": 0.60, "weight": 0.01,
    },
    {
        "name": "Extreme cold (N. Plains)",
        "temp": (5, 10), "wind": (18, 7), "precip": (15, 10),
        "vis": (6, 3), "humid": (45, 15), "day_pct": 0.55, "weight": 0.01,
    },
    {
        "name": "Extreme heat (SW desert)",
        "temp": (108, 6), "wind": (8, 4), "precip": (5, 5),
        "vis": (9, 1), "humid": (20, 8), "day_pct": 0.90, "weight": 0.02,
    },
    {
        "name": "Pleasant evening ride",
        "temp": (70, 5), "wind": (6, 3), "precip": (8, 6),
        "vis": (9, 1), "humid": (50, 10), "day_pct": 0.10, "weight": 0.08,
    },
    {
        "name": "Overcast drizzle",
        "temp": (55, 7), "wind": (10, 4), "precip": (45, 15),
        "vis": (6, 2), "humid": (75, 10), "day_pct": 0.65, "weight": 0.09,
    },
]


def _truncated_normal(rng, mean, std, low, high, size=1):
    """Draw from a normal distribution, clamped to [low, high]."""
    vals = rng.normal(mean, std, size)
    return np.clip(vals, low, high)


def generate_sample(archetype: dict, rng: np.random.Generator) -> dict:
    """Draw one correlated weather sample from an archetype."""
    temp = _truncated_normal(rng, *archetype["temp"], -30, 130)[0]
    wind_speed = _truncated_normal(rng, *archetype["wind"], 0, 60)[0]
    precip_prob = _truncated_normal(rng, *archetype["precip"], 0, 100)[0]
    visibility = _truncated_normal(rng, *archetype["vis"], 0.1, 10)[0]
    humidity = _truncated_normal(rng, *archetype["humid"], 5, 100)[0]
    is_day = 1.0 if rng.random() < archetype["day_pct"] else 0.0

    # --- Cross-feature correlations ---

    # High precip drives humidity up and visibility down
    if precip_prob > 40:
        humidity = min(100, humidity + (precip_prob - 40) * 0.2)
        visibility = max(0.1, visibility - (precip_prob - 40) * 0.03)

    # Wind gusts: scale with sustained wind, add random gust factor
    gust_factor = 1.2 + rng.exponential(0.15)
    wind_gust = wind_speed * gust_factor + rng.exponential(2)
    wind_gust = max(wind_speed, min(wind_gust, 80))
    gust_delta = wind_gust - wind_speed

    # Apparent temperature using NWS formulas
    app_temp = apparent_temperature(temp, wind_speed, humidity)

    return {
        "temp": round(temp, 1),
        "wind_speed": round(wind_speed, 1),
        "precip_prob": round(precip_prob, 1),
        "visibility": round(visibility, 2),
        "humidity": round(humidity, 1),
        "is_day": is_day,
        "wind_gust": round(wind_gust, 1),
        "gust_delta": round(gust_delta, 1),
        "apparent_temp": round(app_temp, 1),
    }


# ---------------------------------------------------------------------------
# Expert Ride Score Calculator — research-backed thresholds
# ---------------------------------------------------------------------------

def calculate_ride_score(row: dict) -> float:
    """
    Calculate a motorcycle ride quality score (0-100) from weather features.

    Thresholds based on:
    - Temperature: 50°F minimum acceptable (TRO.bike, MSF), 62-78°F ideal
    - Wind: 15 mph "windy" threshold, 25+ mph "hazardous" (MSF, TRO.bike)
    - Visibility: 2 miles critical threshold (FHWA fog crash data)
    - Precipitation: rain presence is major crash risk factor (IIHS)
    - Night: significantly increased risk (reduced visibility, wildlife, fatigue)
    """
    score = 100.0
    t = row["apparent_temp"]

    # === DEAL-BREAKERS — cap score very low ===
    if (t <= 0 or t >= 125 or
            row["wind_speed"] >= 45 or
            row["wind_gust"] >= 65 or
            row["visibility"] < 0.25):
        return max(0, min(8, np.random.uniform(0, 8)))

    # === TEMPERATURE (9 zones) ===
    # Use subtractive penalties for temperature to avoid excessive stacking
    if 62 <= t <= 78:
        pass  # Ideal — no penalty
    elif 78 < t <= 85:
        score -= 10
    elif 85 < t <= 95:
        score -= 20
    elif 95 < t <= 105:
        score -= 40
    elif t > 105:
        score -= 55
    elif 55 <= t < 62:
        score -= 12
    elif 50 <= t < 55:
        score -= 22
    elif 40 <= t < 50:
        score -= 40
    elif 32 <= t < 40:
        score -= 45
    elif t < 32:
        score -= 60

    # === WIND (MSF-aligned thresholds) ===
    ws = row["wind_speed"]
    if ws >= 35:
        score -= 40
    elif ws >= 25:
        score -= 30
    elif ws >= 20:
        score -= 22
    elif ws >= 15:
        score -= 12

    # Gust instability penalty
    gd = row["gust_delta"]
    if gd >= 25:
        score -= 25
    elif gd >= 18:
        score -= 15
    elif gd >= 12:
        score -= 8

    # === PRECIPITATION ===
    pp = row["precip_prob"]
    if pp >= 80:
        score -= 30
    elif pp >= 60:
        score -= 25
    elif pp >= 40:
        score -= 22
    elif pp >= 25:
        score -= 14
    elif pp >= 15:
        score -= 9

    # === VISIBILITY (FHWA threshold at 2 miles) ===
    vis = row["visibility"]
    if vis < 0.5:
        score -= 40
    elif vis < 1.0:
        score -= 30
    elif vis < 2.0:
        score -= 25
    elif vis < 4.0:
        score -= 15
    elif vis < 6.0:
        score -= 7

    # === HUMIDITY discomfort ===
    h = row["humidity"]
    if h > 90:
        score -= 8
    elif h > 80:
        score -= 4

    # === NIGHT PENALTY (~20% reduction) ===
    if row["is_day"] == 0:
        score *= 0.78

    # Add noise to avoid perfectly deterministic scores
    score += np.random.uniform(-3, 3)

    return round(max(0, min(100, score)), 1)


# ---------------------------------------------------------------------------
# Main Generation Pipeline
# ---------------------------------------------------------------------------

def generate_synthetic_data(samples: int = 15000, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic ride score training data using weather archetypes."""
    rng = np.random.default_rng(seed)
    np.random.seed(seed)  # for numpy functions in calculate_ride_score

    # Compute per-archetype sample counts from weights
    weights = np.array([a["weight"] for a in ARCHETYPES])
    weights = weights / weights.sum()  # normalize
    counts = np.round(weights * samples).astype(int)
    # Adjust last archetype to hit exact sample count
    counts[-1] = samples - counts[:-1].sum()

    rows = []
    for archetype, count in zip(ARCHETYPES, counts):
        for _ in range(count):
            sample = generate_sample(archetype, rng)
            sample["ride_score"] = calculate_ride_score(sample)
            rows.append(sample)

    df = pd.DataFrame(rows)
    # Shuffle so archetypes aren't grouped
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    df = generate_synthetic_data(samples=15000)

    # --- Diagnostics ---
    print(f"Generated {len(df)} samples\n")
    print("Score distribution:")
    print(f"  Mean:   {df['ride_score'].mean():.1f}")
    print(f"  Median: {df['ride_score'].median():.1f}")
    print(f"  Std:    {df['ride_score'].std():.1f}")
    print()

    bins = [(80, 100, "Excellent"), (60, 80, "Good"), (40, 60, "Fair"),
            (20, 40, "Poor"), (0, 20, "Dangerous")]
    for low, high, label in bins:
        pct = ((df["ride_score"] >= low) & (df["ride_score"] < high)).mean() * 100
        print(f"  {label:10s} ({low:3d}-{high:3d}): {pct:5.1f}%")

    print(f"\nFeature correlations with ride_score:")
    for col in df.columns:
        if col != "ride_score":
            corr = df[col].corr(df["ride_score"])
            print(f"  {col:15s}: {corr:+.3f}")

    # Save
    output_file = "syntheticRideScoreData.csv"
    df.to_csv(output_file, index=False)
    print(f"\nSaved to {output_file}")
