from dotenv import load_dotenv
from directions import computeRoutes
from weather import getWeather


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
    print("Weather Recieved")

    # print(points_to_forecast_map)
    # TODO I would also like to use progress bars instead of printing end messages

    # TODO compile forecasts and get a suggest gear I may need.
    # note: right now the forecasts I get are for a couple of days, and do not match to the exact time I will reach a destination. In the future I want to get time to each coordinate, and use that info to get the appropriate weather at that time so that I can better predict what gear is actually needed. For example if I'm going to arrive at a set of coordinates after a rain storm has already passed I probably don't need to bring my rain jacket.
    print("TODO Calculating gear needed")
    print("TODO The following gear is needed for your ride:")


if __name__ == "__main__":
    main()
