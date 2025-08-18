from dotenv import load_dotenv
from directions import computeRoutes
from weather import getWeather
from gearSuggester import suggestGear
from tqdm import tqdm
from db import init_db_pool, create_tables, close_pool
from cache import close_redis
from fastapi import FastAPI
from pydantic import BaseModel


MESSAGE_SEPARATOR = "=============================================="

app = FastAPI()

@app.on_event("startup")
def startupEvent():
    print("Welcome to Motorcycle Weather")
    print(MESSAGE_SEPARATOR)

    load_dotenv()
    init_db_pool()
    create_tables()
    print("Environment loaded, Database pool initialized, and tables ensured.")


def shutdownEvent():
    print("Shutting down service...")
    close_pool()
    close_redis()
    print("Database pool and Redis closed.")

class MotorcycleWeatherRequest(BaseModel):
    origin: str
    destination: str

@app.post("/motorcycleWeather/")
def motorcycleWeather(request: MotorcycleWeatherRequest):
    locations = []
    locations.append((request.origin, request.destination))

    print(f"Getting weather info for your route from {request.origin} to {request.destination}")
    print(MESSAGE_SEPARATOR)

    # Get directions between two locations
    route = computeRoutes(locations)

    # Get weather for directions. Directions are saved as set of distances and coordinates.
    getWeather(route)

    suggested_gear = suggestGear(route)
    print(f"The following gear is needed for your ride: {suggested_gear}")

    # Build result
    result = {}
    result["status"] = 200
    result["suggestedGear"] = suggested_gear

    return result


