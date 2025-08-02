from dotenv import load_dotenv
from directions import computeRoutes
from weather import getWeather
from gearSuggester import suggestGear


MESSAGE_SEPARATOR = "=============================================="

def main():
    load_dotenv()

    print("Welcome to Motorcycle Weather")
    print(MESSAGE_SEPARATOR)

    # Get directions between two locations
    origin = "1600 Amphitheatre Parkway, Mountain View, CA"
    destination = "450 Serra Mall, Stanford, CA"
    print(f"Getting weather info for your route from {origin} to {destination}")
    print(MESSAGE_SEPARATOR)

    print("Getting route")
    route = computeRoutes(origin, destination)
    print("Route Received")
  
    # Get weather for directions. Directions are saved as set of distances and coordinates.
    print("Getting weather")
    points_to_forecast_map = getWeather(route)
    print("Weather Received")

    # TODO: I would also like to use progress bars instead of printing end messages

    print("Calculating gear needed")
    suggested_gear = suggestGear(points_to_forecast_map)
    print("The following gear is needed for your ride:")
    for gear in suggested_gear:
       print(gear)


    # TODO: impliment a db so that I don't have to keep getting the same data over and over. Also need to figure out how weather.com is giving my TTL of weather for each point as well as coordinate to point TTL.


if __name__ == "__main__":
    main()
