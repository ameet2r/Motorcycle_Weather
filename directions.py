import requests
import os
import polyline


class Coordinates:
    def __init__(self, latitude: str, longitude: str):
        self.latitude = latitude
        self.longitude = longitude

    def __eq__(self, other):
        return isinstance(other, Coordinates) and self.latitude == other.latitude and self.longitude == other.longitude

    def __hash__(self):
        return hash((self.latitude, self.longitude))

    def __repr__(self):
        return f"Coordinates({self.latitude}, {self.longitude})"


class Step:
    def __init__(self, distanceMeters: str, polyline: str, coordinates: list[Coordinates]):
        self.distance_meters = distanceMeters
        self.polyline = polyline
        self.coordinates = coordinates


def computeRoutes(origin: str, destination: str) -> list[Step]:
    #TODO: need to get travel time and arrival time at each coordinate
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

    if response.status_code == 200:
        for route in response_json["routes"]:
            for leg in route["legs"]:
                for step in leg["steps"]:
                    encoded_polyline = step["polyline"]["encodedPolyline"]
                    decoded_polyline = polyline.decode(encoded_polyline)
                    coordinates_list = []
                    for coordinate_str_pair in decoded_polyline:
                        coordinates_list.append(Coordinates(latitude=str(coordinate_str_pair[0]), longitude=str(coordinate_str_pair[1])))

                    new_step = Step(step["distanceMeters"], encoded_polyline, coordinates_list)
                    steps.append(new_step)

    #TODO: need to update logic to include error message if I don't get the route correctly.
    return steps


