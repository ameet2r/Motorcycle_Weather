import logging
import time
from typing import Optional, Callable, Any, Literal
from functools import wraps
from fastapi import Request, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth
from .firebase_admin import verify_firebase_token, verify_app_check_token, get_user_info
from .firestore_service import get_or_create_user

MembershipTier = Literal["free", "plus", "pro"]

logger = logging.getLogger(__name__)

# In-memory user document cache with 5-minute TTL
_USER_CACHE_TTL = 300  # seconds
_user_cache: dict[str, tuple[dict, float]] = {}  # uid -> (user_doc, expires_at)


def _get_cached_user(uid: str, email: str | None) -> dict:
    """Get user document from cache or Firestore, caching the result."""
    now = time.monotonic()
    cached = _user_cache.get(uid)
    if cached is not None:
        user_doc, expires_at = cached
        if now < expires_at:
            return user_doc
        del _user_cache[uid]

    user_doc = get_or_create_user(uid, email)
    _user_cache[uid] = (user_doc, now + _USER_CACHE_TTL)
    return user_doc


def invalidate_user_cache(uid: str) -> None:
    """Remove a user from the in-memory cache (call after membership changes)."""
    _user_cache.pop(uid, None)

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
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_firebase_appcheck: Optional[str] = Header(None, alias="X-Firebase-AppCheck")
) -> Optional[dict]:
    """
    FastAPI dependency to get current authenticated user with App Check verification

    Args:
        request: FastAPI request object
        credentials: HTTP Bearer token credentials
        x_firebase_appcheck: Firebase App Check token from header

    Returns:
        dict: User information if authenticated, None if on excluded path

    Raises:
        HTTPException: If authentication or App Check verification fails
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

    # Check if App Check header is present
    if not x_firebase_appcheck:
        logger.warning(f"Missing X-Firebase-AppCheck header for path: {request.url.path}")
        raise HTTPException(
            status_code=403,
            detail={
                "message": "App Check token required",
                "error_code": "APP_CHECK_TOKEN_MISSING"
            }
        )

    try:
        # Verify the Firebase App Check token first
        await verify_app_check_token(x_firebase_appcheck)

        # Then verify the Firebase ID token
        decoded_token = await verify_firebase_token(credentials.credentials)

        # Extract user information
        user_info = get_user_info(decoded_token)

        logger.info(f"User authenticated successfully with App Check: {user_info['uid']}")
        return user_info

    except ValueError as e:
        # App Check verification errors
        error_msg = str(e)
        if "App Check" in error_msg:
            logger.warning(f"App Check verification failed: {e}")
            raise HTTPException(
                status_code=403,
                detail={
                    "message": error_msg,
                    "error_code": "APP_CHECK_TOKEN_INVALID"
                }
            )
        # Other ValueError (token format issues)
        logger.warning(f"Invalid token format: {e}")
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Invalid token format",
                "error_code": "AUTH_TOKEN_MALFORMED"
            }
        )
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
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_firebase_appcheck: Optional[str] = Header(None, alias="X-Firebase-AppCheck")
) -> dict:
    """
    FastAPI dependency that requires authentication and fetches user document from Firestore

    Args:
        request: FastAPI request object
        credentials: HTTP Bearer token credentials
        x_firebase_appcheck: Firebase App Check token from header

    Returns:
        dict: User information including membershipTier from Firestore

    Raises:
        HTTPException: If authentication or App Check verification fails or user document cannot be accessed
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

    # Always require App Check, regardless of path
    if not x_firebase_appcheck:
        logger.warning(f"Missing X-Firebase-AppCheck header for protected endpoint: {request.url.path}")
        raise HTTPException(
            status_code=403,
            detail={
                "message": "App Check token required",
                "error_code": "APP_CHECK_TOKEN_MISSING"
            }
        )

    try:
        # Verify the Firebase App Check token first
        await verify_app_check_token(x_firebase_appcheck)

        # Then verify the Firebase ID token
        decoded_token = await verify_firebase_token(credentials.credentials)

        # Extract user information from token
        user_info = get_user_info(decoded_token)
        uid = user_info['uid']
        email = user_info.get('email')

        # Fetch or create user document from cache/Firestore
        try:
            user_doc = _get_cached_user(uid, email)
        except Exception as e:
            logger.error(f"Failed to fetch/create user document for UID {uid}: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Failed to access user data",
                    "error_code": "USER_DATA_ERROR"
                }
            )

        # Merge Firebase user info with Firestore user data
        complete_user_info = {
            **user_info,
            'membershipTier': user_doc.get('membershipTier', 'free'),
            'createdAt': user_doc.get('createdAt')
        }

        logger.info(f"User authenticated for protected endpoint: {uid} (tier: {complete_user_info['membershipTier']})")
        return complete_user_info

    except ValueError as e:
        # App Check verification errors
        error_msg = str(e)
        if "App Check" in error_msg:
            logger.warning(f"App Check verification failed for protected endpoint: {e}")
            raise HTTPException(
                status_code=403,
                detail={
                    "message": error_msg,
                    "error_code": "APP_CHECK_TOKEN_INVALID"
                }
            )
        # Other ValueError (token format issues)
        logger.warning(f"Invalid token format for protected endpoint: {e}")
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Invalid token format",
                "error_code": "AUTH_TOKEN_MALFORMED"
            }
        )
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
    except HTTPException:
        # Re-raise HTTPExceptions (like the one from user data error above)
        raise
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


def require_membership_tier(required_tier: MembershipTier):
    """
    Factory function to create a dependency that checks membership tier

    Args:
        required_tier: The minimum membership tier required ('free', 'plus', 'pro')

    Returns:
        FastAPI dependency function
    """
    tier_hierarchy = {'free': 0, 'plus': 1, 'pro': 2}

    async def check_tier(user: dict = Depends(get_authenticated_user)) -> dict:
        """
        Check if user has required membership tier

        Args:
            user: User information from authentication

        Returns:
            dict: User information if tier requirement met

        Raises:
            HTTPException: If user's tier is insufficient
        """
        user_tier = user.get('membershipTier', 'free')
        user_tier_level = tier_hierarchy.get(user_tier, 0)
        required_level = tier_hierarchy.get(required_tier, 0)

        if user_tier_level < required_level:
            logger.warning(f"Access denied for user {user['uid']} (tier: {user_tier}) to {required_tier}+ content")
            raise HTTPException(
                status_code=403,
                detail={
                    "message": f"This feature requires {required_tier} membership or higher",
                    "error_code": "INSUFFICIENT_TIER",
                    "user_tier": user_tier,
                    "required_tier": required_tier
                }
            )

        return user

    return check_tier


# Pre-configured tier dependencies for convenience
require_free_tier = require_membership_tier('free')
require_plus_tier = require_membership_tier('plus')
require_pro_tier = require_membership_tier('pro')


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