from dotenv import load_dotenv
from directions import computeRoutes
from weather import getWeather
from gearSuggester import suggestGear
from tqdm import tqdm


MESSAGE_SEPARATOR = "=============================================="

# def download_podcast(url, filename):
#     response = requests.get(url, stream=True)

#     if response.status_code == 200:
#         total_size = int(response.headers.get("content-length", 0)) # Get file size
#         block_size = 1024 # Download in 1KB chuncks
#         with open(filename, "wb") as file, tqdm(
#             desc=filename,
#             total=total_size,
#             unit="B",
#             unit_scale=True,
#             unit_divisor=block_size
#         ) as bar:
#             for chunk in response.iter_content(block_size):
#                 file.write(chunk)
#                 bar.update(len(chunk))
#         print(f"{filename} downloaded successfully")
#     else:
#         print(f"{filename} failed to download. Status code: {response.status_code}")
  
def main():
    load_dotenv()

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
    points_to_forecast_map = getWeather(route)

    suggested_gear = suggestGear(points_to_forecast_map)
    print("The following gear is needed for your ride:")
    for gear in suggested_gear:
       print(gear)


    # TODO: impliment a db so that I don't have to keep getting the same data over and over. Also need to figure out how weather.com is giving my TTL of weather for each point as well as coordinate to point TTL.


if __name__ == "__main__":
    main()
