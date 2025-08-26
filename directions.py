import math
import requests
import os
import polyline
from tqdm import tqdm
from datetime import datetime, timedelta, timezone
from coordinates import Step, Coordinates
from requestTypes import DirectionsToWeatherRequest, Waypoint


# Function to compute distance (meters) between two lat/lon points
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(d_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def generateLocationRequestData(waypoint: Waypoint) -> dict|str:
    waypoint_data = {}
    waypoint_location = waypoint.location
    if waypoint_location:
        waypoint_data = {
            "location": {
                "latLng": {
                    "latitude": waypoint_location.latLng.latitude,
                    "longitude": waypoint_location.latLng.longitude
                }
            }
        }
    elif waypoint.placeId:
        waypoint_data = {
            "placeId": waypoint.placeId
        }
    elif waypoint.address:
        waypoint_data = { 
            "address": waypoint.address
        }

    return waypoint_data


def generateRequestData(request: DirectionsToWeatherRequest) -> dict:
    result = {}

    result["origin"] = generateLocationRequestData(request.origin)

    result["destination"] = generateLocationRequestData(request.destination)

    intermediates = request.intermediates
    if len(intermediates):
        intermediates_data = []
        for intermediate_waypoint in intermediates:
            intermediates_data.append(generateLocationRequestData(intermediate_waypoint))
        result["intermediates"] = intermediates_data

    result["routeModifiers"] = {"avoidTolls": True}
    result["travelMode"] = "DRIVE"
    result["languageCode"] = "en-US"
    result["units"] = "METRIC"

    if request.trafficAware:
        result["routingPreference"] = "TRAFFIC_AWARE"

    return result


def computeRoutes(request: DirectionsToWeatherRequest) -> tuple:
    result = []
    coords = []
    
    try:
        for _ in tqdm(range(1), desc="Fetching Routes"):
            url = "https://routes.googleapis.com/directions/v2:computeRoutes"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": os.getenv("GOOGLE_ROUTES_API_KEY"),
                "X-Goog-FieldMask": "routes.legs.steps.polyline.encodedPolyline,routes.legs.steps.distanceMeters,routes.legs.steps.staticDuration"
            }
            print(f"request={request}")
            generated_data = generateRequestData(request)

            print(f"request to computeRoutes: url={url}, headers={headers}, json={generated_data}")
            response = requests.post(url, headers=headers, json=generated_data)
            response_json = response.json()

            # Get list of coordinates, distances to each
            steps = []

            current_time = datetime.now().astimezone(timezone.utc)
            if response.status_code == 200:
                for route in response_json["routes"]:
                    for leg in route["legs"]:
                        for step in leg["steps"]:
                            duration_seconds = int(step["staticDuration"][0:-1:1])
                            distance_meters = step["distanceMeters"]
                            encoded_polyline = step["polyline"]["encodedPolyline"]
                            decoded_polyline = polyline.decode(encoded_polyline)

                            # Compute distances between coordinates
                            segment_distances = []
                            total_distance = 0
                            for idx in range(1, len(decoded_polyline)):
                                distance = haversine(decoded_polyline[idx-1][0], decoded_polyline[idx-1][1], 
                                                     decoded_polyline[idx][0], decoded_polyline[idx][1])
                                segment_distances.append(distance)
                                total_distance += distance

                            # Compute ETA per coordinate weighted by distance
                            coordinates_list = []
                            step_time = current_time
                            for i, (latitude, longitude) in enumerate(decoded_polyline):
                                if i > 0:
                                    segment_duration = duration_seconds * (segment_distances[i-1] / total_distance)
                                    step_time += timedelta(seconds=segment_duration)
                                new_coordinate = Coordinates(latitude=str(latitude), longitude=str(longitude), eta=step_time.replace(tzinfo=timezone.utc))
                                coordinates_list.append(new_coordinate)
                                coords.append(new_coordinate)
                            
                            current_time += timedelta(seconds=duration_seconds)
                            new_step = Step(distance_meters, encoded_polyline, coordinates_list)
                            steps.append(new_step)

            else:
                print(f"status_code={response.status_code}, error={response.reason}")
            result = steps
    except:
        print(f"Error retrieving route")

    return (result, coords)



