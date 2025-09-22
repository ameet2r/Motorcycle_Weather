import logging
from typing import Optional, Callable, Any
from functools import wraps
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth
from .firebase_admin import verify_firebase_token, get_user_info

logger = logging.getLogger(__name__)

# FastAPI security scheme for Bearer token
security = HTTPBearer(auto_error=False)

# Paths that don't require authentication
EXCLUDED_PATHS = [
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc"
]

class AuthenticationError(Exception):
    """Custom exception for authentication errors"""
    def __init__(self, message: str, error_code: str = "AUTH_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    FastAPI dependency to get current authenticated user
    
    Args:
        request: FastAPI request object
        credentials: HTTP Bearer token credentials
        
    Returns:
        dict: User information if authenticated, None if on excluded path
        
    Raises:
        HTTPException: If authentication fails
    """
    # Skip authentication for excluded paths
    if request.url.path in EXCLUDED_PATHS:
        return None
    
    # Check if Authorization header is present
    if not credentials:
        logger.warning(f"Missing Authorization header for path: {request.url.path}")
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Authorization header required",
                "error_code": "AUTH_TOKEN_MISSING"
            }
        )
    
    try:
        # Verify the Firebase ID token
        decoded_token = await verify_firebase_token(credentials.credentials)
        
        # Extract user information
        user_info = get_user_info(decoded_token)
        
        logger.info(f"User authenticated successfully: {user_info['uid']}")
        return user_info
        
    except auth.InvalidIdTokenError:
        logger.warning("Invalid Firebase ID token provided")
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Invalid authentication token",
                "error_code": "AUTH_TOKEN_INVALID"
            }
        )
    except auth.ExpiredIdTokenError:
        logger.warning("Expired Firebase ID token provided")
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Authentication token has expired",
                "error_code": "AUTH_TOKEN_EXPIRED"
            }
        )
    except auth.RevokedIdTokenError:
        logger.warning("Revoked Firebase ID token provided")
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Authentication token has been revoked",
                "error_code": "AUTH_TOKEN_REVOKED"
            }
        )
    except ValueError as e:
        logger.warning(f"Invalid token format: {e}")
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Invalid token format",
                "error_code": "AUTH_TOKEN_MALFORMED"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected authentication error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal authentication error",
                "error_code": "AUTH_INTERNAL_ERROR"
            }
        )


async def get_authenticated_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    FastAPI dependency that requires authentication (no excluded paths)
    
    Args:
        request: FastAPI request object
        credentials: HTTP Bearer token credentials
        
    Returns:
        dict: User information
        
    Raises:
        HTTPException: If authentication fails
    """
    # Always require authentication, regardless of path
    if not credentials:
        logger.warning(f"Missing Authorization header for protected endpoint: {request.url.path}")
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Authentication required",
                "error_code": "AUTH_TOKEN_MISSING"
            }
        )
    
    try:
        # Verify the Firebase ID token
        decoded_token = await verify_firebase_token(credentials.credentials)
        
        # Extract user information
        user_info = get_user_info(decoded_token)
        
        logger.info(f"User authenticated for protected endpoint: {user_info['uid']}")
        return user_info
        
    except auth.InvalidIdTokenError:
        logger.warning("Invalid Firebase ID token for protected endpoint")
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Invalid authentication token",
                "error_code": "AUTH_TOKEN_INVALID"
            }
        )
    except auth.ExpiredIdTokenError:
        logger.warning("Expired Firebase ID token for protected endpoint")
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Authentication token has expired",
                "error_code": "AUTH_TOKEN_EXPIRED"
            }
        )
    except auth.RevokedIdTokenError:
        logger.warning("Revoked Firebase ID token for protected endpoint")
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Authentication token has been revoked",
                "error_code": "AUTH_TOKEN_REVOKED"
            }
        )
    except ValueError as e:
        logger.warning(f"Invalid token format for protected endpoint: {e}")
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Invalid token format",
                "error_code": "AUTH_TOKEN_MALFORMED"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected authentication error for protected endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal authentication error",
                "error_code": "AUTH_INTERNAL_ERROR"
            }
        )


def require_auth(func: Callable) -> Callable:
    """
    Decorator to require authentication for endpoint functions
    
    Usage:
        @app.post("/protected-endpoint")
        @require_auth
        async def protected_endpoint(user: dict = Depends(get_authenticated_user)):
            return {"message": f"Hello {user['email']}"}
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    
    return wrapper


class AuthMiddleware:
    """
    Authentication middleware for FastAPI
    
    This middleware can be used to add authentication to all routes,
    but currently we're using dependency injection instead for more granular control.
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        # For now, we're using dependency injection instead of middleware
        # This class is kept for potential future use
        await self.app(scope, receive, send)