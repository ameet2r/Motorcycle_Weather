import os
import logging
from typing import Optional
import firebase_admin
from firebase_admin import credentials, auth, app_check
from google.auth.exceptions import GoogleAuthError

logger = logging.getLogger(__name__)

# Global Firebase app instance
_firebase_app: Optional[firebase_admin.App] = None

def get_firebase_app() -> firebase_admin.App:
    """Get Firebase Admin SDK app instance with lazy initialization"""
    global _firebase_app
    
    if _firebase_app is not None:
        return _firebase_app
    
    try:
        # Check if Firebase app is already initialized
        _firebase_app = firebase_admin.get_app()
        logger.info("Using existing Firebase app instance")
        return _firebase_app
    except ValueError:
        # App not initialized, create new one
        pass
    
    try:
        # Use the same service account credentials as Firestore
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        
        if not project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set")
        
        if cred_path and os.path.exists(cred_path):
            # Use service account file
            cred = credentials.Certificate(cred_path)
            logger.info(f"Initializing Firebase with service account: {cred_path}")
        else:
            # Use default credentials (for Railway deployment with JSON env var)
            cred = credentials.ApplicationDefault()
            logger.info("Initializing Firebase with application default credentials")
        
        _firebase_app = firebase_admin.initialize_app(cred, {
            'projectId': project_id
        })
        
        logger.info(f"Firebase Admin SDK initialized successfully for project: {project_id}")
        return _firebase_app
        
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        raise


async def verify_firebase_token(id_token: str) -> dict:
    """
    Verify Firebase ID token and return decoded claims
    
    Args:
        id_token: Firebase ID token from client
        
    Returns:
        dict: Decoded token claims containing user info
        
    Raises:
        auth.InvalidIdTokenError: If token is invalid
        auth.ExpiredIdTokenError: If token is expired
        auth.RevokedIdTokenError: If token is revoked
        ValueError: If token format is invalid
    """
    if not id_token or not isinstance(id_token, str):
        raise ValueError("Invalid token format")
    
    try:
        # Get Firebase app instance
        app = get_firebase_app()
        
        # Verify the ID token
        decoded_token = auth.verify_id_token(id_token, app=app)
        
        logger.debug(f"Token verified successfully for user: {decoded_token.get('uid')}")
        return decoded_token
        
    except auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid ID token: {e}")
        raise
    except auth.ExpiredIdTokenError as e:
        logger.warning(f"Expired ID token: {e}")
        raise
    except auth.RevokedIdTokenError as e:
        logger.warning(f"Revoked ID token: {e}")
        raise
    except GoogleAuthError as e:
        logger.error(f"Google Auth error during token verification: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {e}")
        raise


async def verify_app_check_token(app_check_token: str) -> dict:
    """
    Verify Firebase App Check token

    Args:
        app_check_token: Firebase App Check token from client

    Returns:
        dict: Decoded App Check token claims

    Raises:
        ValueError: If token format is invalid or verification fails
    """
    if not app_check_token or not isinstance(app_check_token, str):
        raise ValueError("Invalid App Check token format")

    try:
        # Get Firebase app instance
        firebase_app = get_firebase_app()

        # Verify the App Check token
        decoded_token = app_check.verify_token(app_check_token, app=firebase_app)

        logger.debug(f"App Check token verified successfully for app: {decoded_token.get('app_id')}")
        return decoded_token

    except app_check.InvalidAppCheckTokenError as e:
        logger.warning(f"Invalid App Check token: {e}")
        raise ValueError(f"Invalid App Check token: {e}")
    except app_check.ExpiredAppCheckTokenError as e:
        logger.warning(f"Expired App Check token: {e}")
        raise ValueError(f"Expired App Check token: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during App Check token verification: {e}")
        raise ValueError(f"App Check verification failed: {e}")


def get_user_info(decoded_token: dict) -> dict:
    """
    Extract user information from decoded Firebase token

    Args:
        decoded_token: Decoded Firebase ID token

    Returns:
        dict: User information
    """
    return {
        'uid': decoded_token.get('uid'),
        'email': decoded_token.get('email'),
        'email_verified': decoded_token.get('email_verified', False),
        'name': decoded_token.get('name'),
        'picture': decoded_token.get('picture'),
        'provider_id': decoded_token.get('firebase', {}).get('sign_in_provider'),
        'auth_time': decoded_token.get('auth_time'),
        'exp': decoded_token.get('exp'),
        'iat': decoded_token.get('iat')
    }