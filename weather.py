import requests
import os
from dotenv import load_dotenv
import polyline

class Step:
    def __init__(self, distanceMeters, polyline, coordinates):
        self.distance_meters = distanceMeters
        self.polyline = polyline
        self.coordinates = coordinates


def computeRoutes():
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": os.getenv("GOOGLE_ROUTES_API_KEY"),
        "X-Goog-FieldMask": "routes.legs.steps.polyline.encodedPolyline,routes.legs.steps.distanceMeters"
    }
    data = {
        "origin":{"address": "1600 Amphitheatre Parkway, Mountain View, CA"},
        "destination":{"address": "450 Serra Mall, Stanford, CA"},
        "routeModifiers": {
            "avoidTolls": True
        },
        "travelMode": "DRIVE",
        "languageCode": "en-US",
        "units": "METRIC"
    }
     
    response = requests.post(url, headers=headers, json=data)
    response_json = response.json()

    # Get list of coords and distances to each
    steps = []
    for route in response_json["routes"]:
        for leg in route["legs"]:
            for step in leg["steps"]:
                encoded_polyline = step["polyline"]["encodedPolyline"]
                coordinates = polyline.decode(encoded_polyline)
                new_step = Step(step["distanceMeters"], encoded_polyline, coordinates)
                steps.append(new_step)
    for step in steps:
        print(f"distance_meters={step.distance_meters}, coordinates={step.coordinates}")


def main():
    load_dotenv()

    print("Motorcycle Weather")

    # TODO get directions between two routes
    computeRoutes()
    # TODO coordinates for the many locations on the given route. Maybe only the major cities? I think the weather gives info for areas within a 2.5km radius (need to double check this). Break into these sections.
    
    # TODO get forcast for each set of coordinates. Ideally at the exact time that I will reach each set of coordinates. Maybe using the hourly forecast if that is available?

    # TODO display forecast for each set of coordinates

    # TODO suggest gear that I will need.


if __name__ == "__main__":
    main()

