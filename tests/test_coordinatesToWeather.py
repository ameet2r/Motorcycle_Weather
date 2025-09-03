from fastapi.testclient import TestClient
from main import app
from .response import Response
from datetime import datetime, timedelta, timezone


client = TestClient(app)
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
    assert result.status_code == 200
    assert result.suggested_gear != None


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
    assert result.status_code == 200
    assert result.suggested_gear != None

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
    assert result.status_code == 200
    assert result.suggested_gear != None

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
    assert result.status_code == 200
    assert result.suggested_gear != None


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
    assert result.status_code == 200
    assert result.suggested_gear != None


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
    assert result.status_code == 200
    assert result.suggested_gear != None

#TODO: empty coordinates list




