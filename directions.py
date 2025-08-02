import requests
import os
import polyline


class Step:
    def __init__(self, distanceMeters, polyline, coordinates):
        self.distance_meters = distanceMeters
        self.polyline = polyline
        self.coordinates = coordinates


def computeRoutes(origin: str, destination: str) -> list[Step]:
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": os.getenv("GOOGLE_ROUTES_API_KEY"),
        "X-Goog-FieldMask": "routes.legs.steps.polyline.encodedPolyline,routes.legs.steps.distanceMeters"
    }
    data = {
        "origin":{"address": origin},
        "destination":{"address": destination},
        "routeModifiers": {
            "avoidTolls": True
        },
        "travelMode": "DRIVE",
        "languageCode": "en-US",
        "units": "METRIC"
    }
     
    response = requests.post(url, headers=headers, json=data)
    response_json = response.json()

    # Get list of coordinates and distances to each
    steps = []
    for route in response_json["routes"]:
        for leg in route["legs"]:
            for step in leg["steps"]:
                encoded_polyline = step["polyline"]["encodedPolyline"]
                coordinates = polyline.decode(encoded_polyline)
                new_step = Step(step["distanceMeters"], encoded_polyline, coordinates)
                steps.append(new_step)

    return steps

