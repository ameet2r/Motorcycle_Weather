from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from .app.directions import computeRoutes
from .app.weather import getWeather, filterWeatherData
from tqdm import tqdm
from .app.firestore_service import cleanup_expired_documents
from .app.firebase_admin import get_firebase_app
from .app.auth import get_authenticated_user, require_free_tier, require_plus_tier, require_pro_tier
from firebase_admin import auth
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from .app.coordinates import Coordinates
from .app.requestTypes import CoordsToWeatherRequest, DirectionsToWeatherRequest
from .app.constants import MESSAGE_SEPARATOR
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import os
import logging
import signal
import sys
import tempfile
import atexit

load_dotenv()

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
        logging.getLogger("google.auth").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("absl").setLevel(logging.ERROR)
        logging.getLogger("google.cloud").setLevel(logging.WARNING)
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

# Rate limiting setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startupEvent():
    logger.info("Welcome to Motorcycle Weather API")
    logger.info(f"PORT environment variable: {os.getenv('PORT', 'NOT SET (defaulting to 8000)')}")
    logger.info(f"ENVIRONMENT: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"CORS_ORIGINS: {os.getenv('CORS_ORIGINS', 'NOT SET')}")
    
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
    
    # Initialize Firebase Admin SDK
    try:
        firebase_app = get_firebase_app()
        logger.info("Firebase Admin SDK initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        # Don't raise here - let the app start but auth will fail
        logger.warning("Authentication will not work until Firebase is properly configured")
    
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


async def delete_user_account(user: dict, request: Request) -> dict:
    """
    Delete a user's account from Firebase Authentication and associated data.

    Args:
        user: User information from authentication
        request: FastAPI request object for logging

    Returns:
        dict: Success response with deletion details

    Raises:
        HTTPException: If deletion fails
    """
    uid = user['uid']
    email = user.get('email', 'unknown')

    try:
        # Delete user from Firebase Authentication
        auth.delete_user(uid)
        logger.info(f"Successfully deleted user account: UID={uid}, Email={email}")

        # TODO: Add user data deletion from Firestore when user collections are implemented
        # Example:
        # firestore_service.delete_user_data(uid)

        # TODO: Add Cloud Storage cleanup when user files are implemented
        # Example:
        # await cleanup_user_files(uid)

        # Audit logging
        deletion_time = datetime.now(timezone.utc)
        logger.info(f"AUDIT: User account deleted - UID: {uid}, Email: {email}, "
                   f"Timestamp: {deletion_time.isoformat()}, IP: {get_remote_address(request)}")

        return {
            "message": "Account successfully deleted",
            "deleted_at": deletion_time.isoformat(),
            "user_id": uid
        }

    except auth.UserNotFoundError:
        logger.warning(f"Attempted to delete non-existent user: UID={uid}")
        raise HTTPException(
            status_code=404,
            detail={
                "message": "User account not found",
                "error_code": "USER_NOT_FOUND"
            }
        )
    except auth.InsufficientPermissionError:
        logger.error(f"Insufficient permissions to delete user: UID={uid}")
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Insufficient permissions to delete account",
                "error_code": "INSUFFICIENT_PERMISSIONS"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting user account UID={uid}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal error during account deletion",
                "error_code": "DELETION_FAILED"
            }
        )


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
            from .app.firestore_service import get_firestore_client
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

@app.get("/ping")
async def ping():
   """Simple connectivity check endpoint"""
   return Response(status_code=200)

@app.post("/CoordinatesToWeather/")
async def coordinatesToWeather(
    request: CoordsToWeatherRequest,
    user: dict = Depends(get_authenticated_user)
):
    logger.info(f"Getting weather info for {request} - User: {user['uid']}")

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
        result["user_info"] = {
            "uid": user["uid"],
            "email": user["email"],
            "membershipTier": user["membershipTier"]
        }
    except Exception as e:
        logger.error(f"Error processing weather request for user {user['uid']}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    logger.info(f"result={result} - User: {user['uid']}")
    return result


@app.delete("/user/account")
@limiter.limit("1/hour", key_func=lambda request: request.state.user.get('uid') if hasattr(request.state, 'user') else get_remote_address(request))
async def delete_account(
    request: Request,
    user: dict = Depends(get_authenticated_user)
):
    """
    Delete the authenticated user's account.

    This endpoint permanently deletes the user's account from Firebase Authentication
    and any associated data. This action cannot be undone.

    Rate limited to 1 request per hour per user.
    """
    # Store user in request state for rate limiting key function
    request.state.user = user

    logger.info(f"Account deletion requested by user: {user['uid']} ({user.get('email', 'unknown')})")

    result = await delete_user_account(user, request)

    logger.info(f"Account deletion completed for user: {user['uid']}")
    return result


@app.get("/user/profile")
async def get_user_profile(user: dict = Depends(get_authenticated_user)):
    """
    Get the authenticated user's profile information including membership tier.

    This endpoint should be called by the frontend immediately after user login
    to get the user's current membership tier and profile data.

    Returns:
        dict: User profile information
    """
    return {
        "uid": user["uid"],
        "email": user["email"],
        "email_verified": user.get("email_verified", False),
        "membershipTier": user["membershipTier"],
        "name": user.get("name"),
        "picture": user.get("picture"),
        "createdAt": user.get("createdAt"),
        "auth_time": user.get("auth_time"),
        "last_login": user.get("iat")
    }


@app.get("/free-data")
async def get_free_data(user: dict = Depends(require_free_tier)):
    """
    Example endpoint accessible to all authenticated users (free tier and above)

    Returns basic weather-related data for free users
    """
    return {
        "message": "This is free tier data",
        "user_tier": user["membershipTier"],
        "data": {
            "basic_forecast": "Sunny with a chance of clouds",
            "temperature_range": "60-75°F"
        }
    }


@app.get("/plus-data")
async def get_plus_data(user: dict = Depends(require_plus_tier)):
    """
    Example endpoint accessible to plus and pro users only

    Returns enhanced weather data for paying users
    """
    return {
        "message": "This is plus tier data",
        "user_tier": user["membershipTier"],
        "data": {
            "detailed_forecast": "Sunny with 20% chance of afternoon showers",
            "temperature_range": "62-78°F",
            "humidity": "45-65%",
            "wind_speed": "5-15 mph",
            "hourly_breakdown": ["Sunny", "Mostly Sunny", "Partly Cloudy", "Chance of Rain"]
        }
    }


@app.get("/pro-data")
async def get_pro_data(user: dict = Depends(require_pro_tier)):
    """
    Example endpoint accessible to pro users only

    Returns premium weather data and analytics
    """
    return {
        "message": "This is pro tier data",
        "user_tier": user["membershipTier"],
        "data": {
            "premium_forecast": "High pressure system bringing clear skies with isolated afternoon thunderstorms",
            "temperature_range": "64-82°F",
            "humidity": "40-70%",
            "wind_speed": "3-18 mph",
            "precipitation_probability": "15%",
            "uv_index": "Moderate (4-6)",
            "air_quality": "Good",
            "hourly_breakdown": [
                {"time": "12:00", "condition": "Sunny", "temp": 72, "precip": 0},
                {"time": "13:00", "condition": "Mostly Sunny", "temp": 75, "precip": 5},
                {"time": "14:00", "condition": "Partly Cloudy", "temp": 78, "precip": 10},
                {"time": "15:00", "condition": "Chance of Rain", "temp": 76, "precip": 25}
            ],
            "analytics": {
                "best_riding_hours": "11:00-15:00",
                "weather_stability": "High",
                "risk_assessment": "Low"
            }
        }
    }



