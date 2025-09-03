from fastapi.testclient import TestClient
from main import app
from .response import Response


client = TestClient(app)
HEADERS = {"Content-Type": "application/json"}


def test_origin_and_destination_and_intermediates_exist():
    data = {
        "origin": { "address": "1600 Amphitheatre Parkway, Mountain View, CA" },
        "intermediates": [{ "address": "Greer Park, 1098 Amarillo Ave, Palo Alto, CA 94303" }, { "address": "Baylands Nature Preserve, Palo Alto, CA 94303" }],
        "destination": { "address": "450 Serra Mall, Stanford, CA" },
        "ignoreEta": False
    }    
    response = client.post("/DirectionsToWeather", headers=HEADERS, json=data)
    result = Response(response.json())

    assert response.status_code == 200
    assert result.status_code == 200
    assert result.suggested_gear != None

def test_origin_and_destination_and_intermediates_ignoreEta_true_exist():
    data = {
        "origin": { "address": "1600 Amphitheatre Parkway, Mountain View, CA" },
        "intermediates": [{ "address": "Greer Park, 1098 Amarillo Ave, Palo Alto, CA 94303" }, { "address": "Baylands Nature Preserve, Palo Alto, CA 94303" }],
        "destination": { "address": "450 Serra Mall, Stanford, CA" },
        "ignoreEta": True 
    }    
    response = client.post("/DirectionsToWeather", headers=HEADERS, json=data)
    result = Response(response.json())

    assert response.status_code == 200
    assert result.status_code == 200
    assert result.suggested_gear != None


def test_origin_and_destinatoin_exist():
    data = {
      "origin": { "address": "1600 Amphitheatre Parkway, Mountain View, CA" },
      "destination": { "address": "450 Serra Mall, Stanford, CA" }
    }
    response = client.post("/DirectionsToWeather", headers=HEADERS, json=data)
    result = Response(response.json())

    assert response.status_code == 200
    assert result.status_code == 200
    assert result.suggested_gear != None
    

def test_only_origin_no_destination():
    data = {
      "origin": { "address": "1600 Amphitheatre Parkway, Mountain View, CA" },
      "destination": { }
    }
    response = client.post("/DirectionsToWeather", headers=HEADERS, json=data)
    result = Response(response.json())

    # assert response.status_code == 200
    assert result.status_code == 400


def test_only_destination_no_origin():
    data = {
      "origin": { },
      "destination": { "address": "450 Serra Mall, Stanford, CA" }
    }
    response = client.post("/DirectionsToWeather", headers=HEADERS, json=data)
    result = Response(response.json())

    assert result.status_code == 400
    

#TODO: Test placeID
#TODO: Test latLng
