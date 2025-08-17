from dotenv import load_dotenv
from directions import computeRoutes
from weather import getWeather
from gearSuggester import suggestGear
from tqdm import tqdm
from db import init_db_pool, create_tables, close_pool
from cache import close_redis


MESSAGE_SEPARATOR = "=============================================="

def startup_event():
    init_db_pool()
    create_tables()
    print("Database pool initialized and tables ensured.")


def shutdown_event():
    print("Shutting down service...")
    close_pool()
    close_redis()
    print("Database pool and Redis closed.")


def main():
    load_dotenv()
    startup_event()

    print("Welcome to Motorcycle Weather")
    print(MESSAGE_SEPARATOR)

    # Get directions between two locations
    locations = []
    origin = "1600 Amphitheatre Parkway, Mountain View, CA"
    destination = "450 Serra Mall, Stanford, CA"
    locations.append((origin, destination))

    print(f"Getting weather info for your route from {origin} to {destination}")
    print(MESSAGE_SEPARATOR)

    route = computeRoutes(locations)

    # Get weather for directions. Directions are saved as set of distances and coordinates.
    getWeather(route)

    suggested_gear = suggestGear(route)
    print("The following gear is needed for your ride:")
    for gear in suggested_gear:
       print(gear)


if __name__ == "__main__":
    main()
