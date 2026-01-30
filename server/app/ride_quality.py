import numpy as np
import os
import re
import logging

logger = logging.getLogger(__name__)

# Global model instance - loaded once at startup
_model = None


def load_model():
    """Load the XGBoost model at server startup. Called from main.py startup event."""
    global _model

    # Search multiple paths for local dev vs Docker
    base_dir = os.path.dirname(__file__)
    candidate_paths = [
        os.path.join(base_dir, '..', '..', 'ride_quality_model_v2.joblib'),  # local dev (server/app/ -> project root)
        os.path.join(base_dir, '..', 'ride_quality_model_v2.joblib'),        # alternate layout
        '/app/ride_quality_model_v2.joblib',                                  # Docker container
    ]

    for path in candidate_paths:
        resolved = os.path.abspath(path)
        if os.path.exists(resolved):
            import joblib
            _model = joblib.load(resolved)
            logger.info(f"Ride quality model loaded from {resolved}")
            return

    logger.warning("Ride quality model file not found. ML scoring will be disabled.")


def get_model():
    """Return the loaded model, or None if not available."""
    return _model


def _parse_wind_speed(wind_str) -> float:
    """Parse numeric wind speed from string like '10 mph' or just a number."""
    if wind_str is None:
        return 0.0
    if isinstance(wind_str, (int, float)):
        return float(wind_str)
    match = re.search(r'(\d+)', str(wind_str))
    return float(match.group(1)) if match else 0.0


def extract_features(period: dict) -> list | None:
    """
    Extract the 9 ML features from a forecast period dict.

    Feature order (must match training data):
        [temp, wind_speed, precip_prob, visibility, humidity,
         is_day, wind_gust, gust_delta, apparent_temp]

    Returns None if critical features are missing.
    """
    try:
        # --- Required features from hourly forecast ---
        temp = period.get("temperature")
        if temp is None:
            return None

        wind_speed_raw = period.get("windSpeed", "0 mph")
        wind_speed = _parse_wind_speed(wind_speed_raw)

        precip_prob_raw = period.get("probabilityOfPrecipitation", {})
        if isinstance(precip_prob_raw, dict):
            precip_prob = precip_prob_raw.get("value", 0) or 0
        else:
            precip_prob = precip_prob_raw if precip_prob_raw is not None else 0

        is_day_raw = period.get("isDaytime", True)

        # --- Humidity: available in hourly forecast as relativeHumidity dict, or from gridpoints merge as flat float ---
        humidity = None
        relative_humidity_raw = period.get("relativeHumidity")
        if isinstance(relative_humidity_raw, dict):
            humidity = relative_humidity_raw.get("value")
        elif isinstance(relative_humidity_raw, (int, float)):
            humidity = float(relative_humidity_raw)
        if humidity is None:
            humidity = period.get("humidity")  # Fallback: gridpoints-merged flat value

        # --- Features from gridpoints (may be missing, use defaults) ---
        visibility = period.get("visibility")
        wind_gust_raw = period.get("windGust")
        apparent_temp = period.get("apparent_temperature")

        # Parse wind gust
        wind_gust = _parse_wind_speed(wind_gust_raw) if wind_gust_raw is not None else None

        # Apply defaults for missing data
        if visibility is None:
            visibility = 10.0  # Default: clear day (10 miles)
        if humidity is None:
            humidity = 50.0  # Default: moderate humidity
        if wind_gust is None:
            wind_gust = wind_speed * 1.3  # Estimate: gusts ~30% above sustained
        if apparent_temp is None:
            apparent_temp = float(temp)  # Fallback to actual temperature

        # Derived feature
        gust_delta = wind_gust - wind_speed

        # Convert is_day to numeric
        is_day_num = 1.0 if is_day_raw else 0.0

        return [
            float(temp),
            float(wind_speed),
            float(precip_prob),
            float(visibility),
            float(humidity),
            is_day_num,
            float(wind_gust),
            float(gust_delta),
            float(apparent_temp)
        ]
    except (TypeError, ValueError, KeyError) as e:
        logger.warning(f"Failed to extract features from period: {e}")
        return None


def score_periods(periods: list[dict]) -> list[dict]:
    """
    Score all periods and add ride_score to each period dict.
    Uses batch prediction for efficiency.
    Modifies periods in place and returns them.
    """
    model = get_model()
    if model is None:
        return periods

    features_list = []
    valid_indices = []

    for i, period in enumerate(periods):
        features = extract_features(period)
        if features is not None:
            features_list.append(features)
            valid_indices.append(i)

    if features_list:
        try:
            feature_array = np.array(features_list)
            scores = model.predict(feature_array)

            for idx, score in zip(valid_indices, scores):
                clamped = round(float(max(0, min(100, score))), 1)
                periods[idx]["ride_score"] = clamped
        except Exception as e:
            logger.warning(f"Batch prediction failed: {e}")

    return periods
