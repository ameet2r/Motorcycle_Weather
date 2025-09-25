import os
from datetime import datetime, timezone
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from typing import Optional, Dict, Any, Literal
import json
import logging

logger = logging.getLogger(__name__)

MembershipTier = Literal["free", "plus", "pro"]

# Global client instance - will be initialized lazily
_db_client = None

def get_firestore_client():
    """Get Firestore client instance with lazy initialization"""
    global _db_client
    
    if _db_client is not None:
        return _db_client
    
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set")    
    _db_client = firestore.Client(project=project_id)
    return _db_client

class FirestoreService:
    """Service class for Firestore operations replacing PostgreSQL and Redis functionality"""

    def __init__(self):
        # Use lazy initialization - get client when needed
        self._db = None
        self.coordinates_collection = "coordinates"
        self.gridpoints_collection = "gridpoints"
        self.forecasts_collection = "forecasts"
        self.users_collection = "users"
    
    @property
    def db(self):
        """Lazy-loaded database client"""
        if self._db is None:
            self._db = get_firestore_client()
        return self._db
    
    def _is_expired(self, expires_at: datetime) -> bool:
        """Check if a document has expired"""
        if not expires_at:
            return True
        return datetime.now(timezone.utc) > expires_at
    
    def _create_coordinate_doc_id(self, latitude: str, longitude: str) -> str:
        """Create document ID for coordinates collection"""
        return f"{latitude}_{longitude}"
    
    def _create_gridpoint_doc_id(self, grid_id: str, grid_x: str, grid_y: str) -> str:
        """Create document ID for gridpoints and forecasts collections"""
        return f"{grid_id}_{grid_x}_{grid_y}"
    
    # Coordinate to Gridpoints operations (replaces coordinate_to_gridpoints table)
    def get_coordinate_to_gridpoints(self, latitude: str, longitude: str) -> Optional[Dict[str, Any]]:
        """Get gridpoint data for coordinates"""
        doc_id = self._create_coordinate_doc_id(latitude, longitude)
        doc_ref = self.db.collection(self.coordinates_collection).document(doc_id)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            # Check if expired
            if not self._is_expired(data.get('expiresAt')):
                return data
            else:
                # Delete expired document
                doc_ref.delete()
        
        return None
    
    def set_coordinate_to_gridpoints(self, latitude: str, longitude: str, 
                                   grid_id: str, grid_x: str, grid_y: str, 
                                   expires_at: datetime) -> None:
        """Store gridpoint data for coordinates"""
        doc_id = self._create_coordinate_doc_id(latitude, longitude)
        doc_ref = self.db.collection(self.coordinates_collection).document(doc_id)
        
        data = {
            'latitude': float(latitude),
            'longitude': float(longitude),
            'gridId': grid_id,
            'gridX': int(grid_x),
            'gridY': int(grid_y),
            'expiresAt': expires_at
        }
        
        doc_ref.set(data)
    
    # Gridpoints to Forecast URL operations (replaces gridpoints_to_forecast_url table)
    def get_gridpoints_to_forecast_url(self, grid_id: str, grid_x: str, grid_y: str) -> Optional[str]:
        """Get forecast URL for gridpoint"""
        doc_id = self._create_gridpoint_doc_id(grid_id, grid_x, grid_y)
        doc_ref = self.db.collection(self.gridpoints_collection).document(doc_id)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            # Check if expired
            if not self._is_expired(data.get('expiresAt')):
                return data.get('forecastUrl')
            else:
                # Delete expired document
                doc_ref.delete()
        
        return None
    
    def set_gridpoints_to_forecast_url(self, grid_id: str, grid_x: str, grid_y: str,
                                     forecast_url: str, expires_at: datetime) -> None:
        """Store forecast URL for gridpoint"""
        doc_id = self._create_gridpoint_doc_id(grid_id, grid_x, grid_y)
        doc_ref = self.db.collection(self.gridpoints_collection).document(doc_id)
        
        data = {
            'gridId': grid_id,
            'gridX': int(grid_x),
            'gridY': int(grid_y),
            'forecastUrl': forecast_url,
            'expiresAt': expires_at
        }
        
        doc_ref.set(data)
    
    # Gridpoints to Forecast operations (replaces gridpoints_to_forecast table)
    def get_gridpoints_to_forecast(self, grid_id: str, grid_x: str, grid_y: str) -> Optional[Dict[str, Any]]:
        """Get forecast data for gridpoint"""
        doc_id = self._create_gridpoint_doc_id(grid_id, grid_x, grid_y)
        doc_ref = self.db.collection(self.forecasts_collection).document(doc_id)
        doc = doc_ref.get()

        if doc.exists:
            data = doc.to_dict()
            # Check if expired
            if not self._is_expired(data.get('expiresAt')):
                forecast_json = data.get('forecast')
                if forecast_json:
                    return json.loads(forecast_json)
            else:
                # Delete expired document
                doc_ref.delete()

        return None
    
    def set_gridpoints_to_forecast(self, grid_id: str, grid_x: str, grid_y: str,
                                 forecast: Dict[str, Any], expires_at: datetime) -> None:
        """Store forecast data for gridpoint"""
        doc_id = self._create_gridpoint_doc_id(grid_id, grid_x, grid_y)
        doc_ref = self.db.collection(self.forecasts_collection).document(doc_id)

        data = {
            'gridId': grid_id,
            'gridX': int(grid_x),
            'gridY': int(grid_y),
            'forecast': json.dumps(forecast),
            'expiresAt': expires_at
        }

        doc_ref.set(data)

    # User document operations
    def get_or_create_user(self, uid: str, email: str) -> Dict[str, Any]:
        """
        Get existing user document or create new one with default 'free' tier

        Args:
            uid: Firebase user ID
            email: User email from Firebase token

        Returns:
            dict: User document data including membershipTier
        """
        doc_ref = self.db.collection(self.users_collection).document(uid)
        doc = doc_ref.get()

        if doc.exists:
            user_data = doc.to_dict()
            logger.info(f"Retrieved existing user document for UID: {uid}")
            return user_data
        else:
            # Create new user document
            user_data = {
                'membershipTier': 'free',
                'email': email,
                'createdAt': datetime.now(timezone.utc)
            }
            doc_ref.set(user_data)
            logger.info(f"Created new user document for UID: {uid} with email: {email}")
            return user_data

    def get_user(self, uid: str) -> Optional[Dict[str, Any]]:
        """
        Get user document by UID

        Args:
            uid: Firebase user ID

        Returns:
            dict or None: User document data if exists
        """
        doc_ref = self.db.collection(self.users_collection).document(uid)
        doc = doc_ref.get()

        if doc.exists:
            return doc.to_dict()
        return None

    def update_user_membership_tier(self, uid: str, tier: MembershipTier) -> bool:
        """
        Update user's membership tier

        Args:
            uid: Firebase user ID
            tier: New membership tier ('free', 'plus', 'pro')

        Returns:
            bool: True if update successful
        """
        if tier not in ['free', 'plus', 'pro']:
            raise ValueError(f"Invalid membership tier: {tier}")

        doc_ref = self.db.collection(self.users_collection).document(uid)
        doc_ref.update({'membershipTier': tier})
        logger.info(f"Updated membership tier for UID {uid} to {tier}")
        return True

    # Utility methods
    def cleanup_expired_documents(self) -> None:
        """Clean up expired documents across all collections"""
        now = datetime.now(timezone.utc)
        
        collections = [
            self.coordinates_collection,
            self.gridpoints_collection, 
            self.forecasts_collection
        ]
        
        for collection_name in collections:
            # Query for expired documents
            expired_docs = (
                self.db.collection(collection_name)
                .where(filter=FieldFilter("expiresAt", "<", now))
                .stream()
            )
            
            # Delete expired documents
            for doc in expired_docs:
                doc.reference.delete()
                print(f"Deleted expired document: {doc.id} from {collection_name}")

# Global service instance
firestore_service = FirestoreService()

# Convenience functions for backward compatibility
def get_coordinate_to_gridpoints(latitude: str, longitude: str) -> Optional[Dict[str, Any]]:
    return firestore_service.get_coordinate_to_gridpoints(latitude, longitude)

def set_coordinate_to_gridpoints(latitude: str, longitude: str, grid_id: str, 
                               grid_x: str, grid_y: str, expires_at: datetime) -> None:
    return firestore_service.set_coordinate_to_gridpoints(latitude, longitude, grid_id, grid_x, grid_y, expires_at)

def get_gridpoints_to_forecast_url(grid_id: str, grid_x: str, grid_y: str) -> Optional[str]:
    return firestore_service.get_gridpoints_to_forecast_url(grid_id, grid_x, grid_y)

def set_gridpoints_to_forecast_url(grid_id: str, grid_x: str, grid_y: str,
                                 forecast_url: str, expires_at: datetime) -> None:
    return firestore_service.set_gridpoints_to_forecast_url(grid_id, grid_x, grid_y, forecast_url, expires_at)

def get_gridpoints_to_forecast(grid_id: str, grid_x: str, grid_y: str) -> Optional[Dict[str, Any]]:
    return firestore_service.get_gridpoints_to_forecast(grid_id, grid_x, grid_y)

def set_gridpoints_to_forecast(grid_id: str, grid_x: str, grid_y: str,
                             forecast: Dict[str, Any], expires_at: datetime) -> None:
    return firestore_service.set_gridpoints_to_forecast(grid_id, grid_x, grid_y, forecast, expires_at)

def cleanup_expired_documents() -> None:
    return firestore_service.cleanup_expired_documents()

# User document convenience functions
def get_or_create_user(uid: str, email: str) -> Dict[str, Any]:
    return firestore_service.get_or_create_user(uid, email)

def get_user(uid: str) -> Optional[Dict[str, Any]]:
    return firestore_service.get_user(uid)

def update_user_membership_tier(uid: str, tier: MembershipTier) -> bool:
    return firestore_service.update_user_membership_tier(uid, tier)