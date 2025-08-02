from dotenv import load_dotenv
from directions import computeRoutes


def main():
    load_dotenv()

    print("Welcome to Motorcycle Weather")

    # Get directions between two routes
    origin = "1600 Amphitheatre Parkway, Mountain View, CA"
    destination = "450 Serra Mall, Stanford, CA"
    print(f"Getting weather info for your route from {origin} to {destination}")

    steps = computeRoutes(origin, destination)
    for step in steps:
        print(f"distance_meters={step.distance_meters}, coordinates={step.coordinates}")

    # TODO coordinates for the many locations on the given route. Maybe only the major cities? I think the weather gives info for areas within a 2.5km radius (need to double check this). Break into these sections.
    
    # TODO get forcast for each set of coordinates. Ideally at the exact time that I will reach each set of coordinates. Maybe using the hourly forecast if that is available?

    # TODO display forecast for each set of coordinates

    # TODO suggest gear that I will need.


if __name__ == "__main__":
    main()

