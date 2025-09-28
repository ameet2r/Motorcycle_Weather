from fastapi.testclient import TestClient
from server.main import app
from server.app.auth import get_authenticated_user
from .response import Response
from datetime import datetime, timedelta, timezone


def mock_get_authenticated_user():
    return {
        "uid": "test_user",
        "email": "test@example.com",
        "membershipTier": "free"
    }


client = TestClient(app)
client.app.dependency_overrides[get_authenticated_user] = mock_get_authenticated_user
HEADERS = {"Content-Type": "application/json"}
CURRENT_TIME = datetime.now().astimezone(timezone.utc).isoformat()

def test_latLng_with_eta_and_ignoreEta_true():
    data = {
        "coordinates": [
          {
            "latLng": {
              "latitude": "37.4258",
              "longitude": "-122.09865",
            },
              "eta": CURRENT_TIME,
          }
        ],
        "ignoreEta": True
      }    
    response = client.post("/CoordinatesToWeather", headers=HEADERS, json=data)
    result = Response(response.json())

    assert response.status_code == 200
    assert result.coordinates_to_forecasts_map != None


def test_latLng_with_eta_and_ignoreEta_false():
    data = {
        "coordinates": [
          {
            "latLng": {
              "latitude": "37.4258",
              "longitude": "-122.09865",
            },
              "eta": CURRENT_TIME,
          }
        ],
        "ignoreEta": False
      }    
    response = client.post("/CoordinatesToWeather", headers=HEADERS, json=data)
    result = Response(response.json())

    assert response.status_code == 200
    assert result.coordinates_to_forecasts_map != None

def test_latLng_with_eta_and_no_ignoreEta():
    data = {
        "coordinates": [
          {
            "latLng": {
              "latitude": "37.4258",
              "longitude": "-122.09865",
            },
              "eta": CURRENT_TIME,
          }
        ]
      }    
    response = client.post("/CoordinatesToWeather", headers=HEADERS, json=data)
    result = Response(response.json())

    assert response.status_code == 200
    assert result.coordinates_to_forecasts_map != None

def test_latLng_without_eta_and_no_ignoreEta():
    data = {
        "coordinates": [
          {
            "latLng": {
              "latitude": "37.4258",
              "longitude": "-122.09865",
            }
          }
        ]
      }    
    response = client.post("/CoordinatesToWeather", headers=HEADERS, json=data)
    result = Response(response.json())

    assert response.status_code == 200
    assert result.coordinates_to_forecasts_map != None


def test_latLng_without_eta_and_ignoreEta_false():
    data = {
        "coordinates": [
          {
            "latLng": {
              "latitude": "37.4258",
              "longitude": "-122.09865",
            }
          }
        ],
        "ignoreEta": False
      }    
    response = client.post("/CoordinatesToWeather", headers=HEADERS, json=data)
    result = Response(response.json())

    assert response.status_code == 200
    assert result.coordinates_to_forecasts_map != None


def test_latLng_without_eta_and_ignoreEta_true():
    data = {
        "coordinates": [
          {
            "latLng": {
              "latitude": "37.4258",
              "longitude": "-122.09865",
            }
          }
        ],
        "ignoreEta": True
      }    
    response = client.post("/CoordinatesToWeather", headers=HEADERS, json=data)
    result = Response(response.json())

    assert response.status_code == 200
    assert result.coordinates_to_forecasts_map != None


def test_empty_coordinates_list():
    data = {
        "coordinates": []
    }
    response = client.post("/CoordinatesToWeather", headers=HEADERS, json=data)
    response_json = response.json()


    assert response.status_code == 400
    assert response_json["detail"] == "No coordinates provided"


def test_coordinates_inside_us():
    data = {
        "coordinates": [
            {
                "latLng": {
                    "latitude": "37.4258",  # Mountain View, CA
                    "longitude": "-122.09865",
                }
            },
            {
                "latLng": {
                    "latitude": "40.7128",  # New York, NY
                    "longitude": "-74.0060",
                }
            },
            {
                "latLng": {
                    "latitude": "21.3069",  # Honolulu, HI
                    "longitude": "-157.8583",
                }
            },
            {
                "latLng": {
                    "latitude": "64.2008",  # Fairbanks, AK
                    "longitude": "-149.4937",
                }
            },
            {
                "latLng": {
                    "latitude": "18.2208",  # Puerto Rico
                    "longitude": "-66.5901",
                }
            },
        ]
    }

    response = client.post("/CoordinatesToWeather", headers=HEADERS, json=data)
    result = Response(response.json())

    assert response.status_code == 200
    assert result.coordinates_to_forecasts_map is not None


def test_coordinates_outside_us():
    data = {
        "coordinates": [
            {
                "latLng": {
                    "latitude": "51.5074",  # London
                    "longitude": "-0.1278",
                }
            },
            {
                "latLng": {
                    "latitude": "-33.8688",  # Sydney
                    "longitude": "151.2093",
                }
            },
            {
                "latLng": {
                    "latitude": "35.6895",  # Tokyo
                    "longitude": "139.6917",
                }
            },
        ]
    }

    response = client.post("/CoordinatesToWeather", headers=HEADERS, json=data)
    response_json = response.json()

    # Extract all error messages
    messages = [item['msg'] for item in response_json['detail']]

    # Make sure error messages for each given latitude/longitude pair mention that coordinates must be within the US
    for msg in messages:
        assert "Coordinates must be within the United States" in msg


def test_coordinates_with_address():
    data = {
        "coordinates": [
            {
                "latLng": {
                    "latitude": "37.4258",
                    "longitude": "-122.09865",
                },
                "address": "123 Main St, Mountain View, CA 94043, USA"
            },
            {
                "latLng": {
                    "latitude": "40.7128",
                    "longitude": "-74.0060",
                }
            }
        ]
    }

    response = client.post("/CoordinatesToWeather", headers=HEADERS, json=data)
    result = Response(response.json())

    assert response.status_code == 200
    assert result.coordinates is not None
    assert len(result.coordinates) == 2

    # First coordinate should have address
    assert "address" in result.coordinates[0]
    assert result.coordinates[0]["address"] == "123 Main St, Mountain View, CA 94043, USA"
    assert result.coordinates[0]["latLng"]["latitude"] == "37.4258"
    assert result.coordinates[0]["latLng"]["longitude"] == "-122.09865"

    # Second coordinate should not have address
    assert "address" not in result.coordinates[1]
    assert result.coordinates[1]["latLng"]["latitude"] == "40.7128"
    assert result.coordinates[1]["latLng"]["longitude"] == "-74.0060"


