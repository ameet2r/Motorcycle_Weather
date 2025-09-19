from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from app.directions import computeRoutes
from app.weather import getWeather, filterWeatherData
from tqdm import tqdm
from app.firestore_service import cleanup_expired_documents
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.coordinates import Coordinates
from app.requestTypes import CoordsToWeatherRequest, DirectionsToWeatherRequest
from app.constants import MESSAGE_SEPARATOR
import os
import logging
import signal
import sys
import tempfile
import atexit


# Configure logging for production
def setup_logging():
    """Configure logging based on environment"""
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "production":
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        # Reduce noise from external libraries
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
    else:
        logging.basicConfig(level=logging.DEBUG)

# Global variable to track temporary credential files for cleanup
temp_credential_files = []

def cleanup_temp_files():
    """Clean up temporary credential files"""
    for temp_file in temp_credential_files:
        try:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
                logging.info(f"Cleaned up temporary credential file: {temp_file}")
        except Exception as e:
            logging.warning(f"Could not clean up temporary file {temp_file}: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logging.info(f"Received signal {signum}, shutting down gracefully...")
    cleanup_temp_files()
    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Register cleanup function to run on exit
atexit.register(cleanup_temp_files)

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Motorcycle Weather API",
    description="Weather forecasting service for motorcycle routes",
    version="1.0.0"
)

# Allow requests from the following locations
origins = os.getenv("CORS_ORIGINS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startupEvent():
    logger.info("Welcome to Motorcycle Weather API")
    logger.info(f"PORT environment variable: {os.getenv('PORT', 'NOT SET (defaulting to 8000)')}")
    logger.info(f"ENVIRONMENT: {os.getenv('ENVIRONMENT', 'development')}")

    load_dotenv()
    
    # Handle Railway credential setup
    creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if creds_json:
        try:
            import json
            # Validate JSON format
            json.loads(creds_json)
            
            # Create temporary file with service account credentials
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write(creds_json)
                temp_credential_files.append(f.name)
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = f.name
                logger.info("Railway credentials configured successfully")
        except json.JSONDecodeError:
            logger.error("Invalid JSON in GOOGLE_APPLICATION_CREDENTIALS_JSON")
            raise ValueError("Invalid JSON in GOOGLE_APPLICATION_CREDENTIALS_JSON")
        except Exception as e:
            logger.error(f"Failed to setup Railway credentials: {e}")
            raise
    
    logger.info("Environment loaded, Firestore client initialized.")
    
    # Optional: Clean up expired documents on startup
    try:
        cleanup_expired_documents()
        logger.info("Cleaned up expired documents from Firestore.")
    except Exception as e:
        logger.warning(f"Could not clean up expired documents: {e}")


@app.on_event("shutdown")
async def shutdownEvent():
    logger.info("Shutting down service...")
    cleanup_temp_files()
    logger.info("Firestore connections closed automatically.")


async def main(request: DirectionsToWeatherRequest):
    logger.info(f"Getting weather info for your route from {request.origin} to {request.destination}")

    result = {}

    if not (request.origin.placeId or request.origin.address or request.origin.location) or not (request.destination.placeId or request.destination.address or request.destination.location):
        raise HTTPException(status_code=400, detail="No locations provided")

    try:
        # Get directions between two locations
        steps, coords = computeRoutes(request)
        logger.info(f"coords after route computed={coords}, steps after route computed={steps}")

        # Get weather for directions. Directions are saved as set of distances and coordinates.
        getWeather(coords)
        logger.info(f"list_of_coordinates after weather retrieved={coords}, and request.ignoreEta={request.ignoreEta}")

        # Filter forecasts
        coordinates_to_forecasts_map = filterWeatherData(coords, request.ignoreEta)
        logger.info(f"coordinates_to_forecasts_map={coordinates_to_forecasts_map}")

        # Build result
        result["coordinates_to_forecasts_map"] = coordinates_to_forecasts_map
    except:
        raise HTTPException(status_code=500, detail="Internal server error")

    logger.info(f"result={result}")
    return result

@app.get("/")
async def root():
    """Root endpoint for basic connectivity test"""
    return {
        "message": "Motorcycle Weather API is running",
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway monitoring"""
    try:
        # Log health check attempt with more details
        logger.info("=== HEALTH CHECK REQUESTED ===")
        logger.info(f"Request received at /health endpoint")
        
        # Basic health check response
        health_response = {
            "status": "healthy",
            "service": "Motorcycle Weather API",
            "environment": os.getenv("ENVIRONMENT", "development"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Check if credentials are properly set
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        
        logger.info(f"GOOGLE_APPLICATION_CREDENTIALS: {'SET' if creds_path else 'NOT SET'}")
        logger.info(f"GOOGLE_CLOUD_PROJECT: {'SET' if project_id else 'NOT SET'}")
        
        if creds_path:
            logger.info(f"Credentials file exists: {os.path.exists(creds_path)}")
        
        # Try to test Firestore connection, but don't fail health check if it fails
        try:
            from app.firestore_service import get_firestore_client
            logger.info("Getting Firestore client...")
            db = get_firestore_client()
            logger.info("Firestore client obtained, testing connection...")
            
            # Simple test to verify Firestore is accessible
            result = db.collection('health_check').limit(1).get()
            logger.info(f"Firestore connection test successful, got {len(list(result))} documents")
            health_response["firestore"] = "connected"
            
        except Exception as firestore_error:
            logger.warning(f"Firestore connection failed during health check: {str(firestore_error)}")
            health_response["firestore"] = f"error: {str(firestore_error)}"
            # Don't fail the health check for Firestore issues - the app can still serve requests
        
        logger.info("Health check completed successfully")
        return health_response
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Service unhealthy: {str(e)}"
        )

@app.post("/CoordinatesToWeather/")
async def coordinatesToWeather(request: CoordsToWeatherRequest):
    logger.info(f"Getting weather info for {request}")

    result = {}
    if len(request.coordinates) == 0:
        raise HTTPException(status_code=400, detail="No coordinates provided")

    try:
        list_of_coordinates = []
        for element in request.coordinates:
            latitude = element.latLng.latitude
            longitude = element.latLng.longitude
           
            coord_eta = None
            if element.eta:
                coord_eta = datetime.fromisoformat(element.eta).astimezone(timezone.utc)
            list_of_coordinates.append(Coordinates(latitude, longitude, coord_eta))
        logger.info(f"list_of_coordinates after list creation={list_of_coordinates}")

        # Get weather for list of Coordinates
        getWeather(list_of_coordinates)
        logger.info(f"list_of_coordinates after weather retrieved={list_of_coordinates}, and request.ignoreEta={request.ignoreEta}")

        # Filter forecasts
        coordinates_to_forecasts_map = filterWeatherData(list_of_coordinates, request.ignoreEta)
        logger.info(f"coordinates_to_forecasts_map={coordinates_to_forecasts_map}")

        # Build result
        result["coordinates_to_forecasts_map"] = coordinates_to_forecasts_map 
    except:
        raise HTTPException(status_code=500, detail="Internal server error")

    logger.info(f"result={result}")
    return result


