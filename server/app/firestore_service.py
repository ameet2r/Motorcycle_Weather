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
        self.searches_collection = "searches"
        self.alerts_collection = "alerts"
    
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

    # Alerts operations (weather alerts caching)
    def get_alerts(self, latitude: str, longitude: str) -> Optional[list]:
        """Get active weather alerts for coordinates"""
        doc_id = self._create_coordinate_doc_id(latitude, longitude)
        doc_ref = self.db.collection(self.alerts_collection).document(doc_id)
        doc = doc_ref.get()

        if doc.exists:
            data = doc.to_dict()
            # Check if expired
            if not self._is_expired(data.get('expiresAt')):
                alerts_json = data.get('alerts')
                if alerts_json:
                    return json.loads(alerts_json)
            else:
                # Delete expired document
                doc_ref.delete()

        return None

    def set_alerts(self, latitude: str, longitude: str, alerts: list, expires_at: datetime) -> None:
        """Store active weather alerts for coordinates"""
        doc_id = self._create_coordinate_doc_id(latitude, longitude)
        doc_ref = self.db.collection(self.alerts_collection).document(doc_id)

        data = {
            'latitude': float(latitude),
            'longitude': float(longitude),
            'alerts': json.dumps(alerts),
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

    def delete_user(self, uid: str) -> bool:
        """
        Delete user document from Firestore

        Args:
            uid: Firebase user ID

        Returns:
            bool: True if deletion successful, False if user not found
        """
        doc_ref = self.db.collection(self.users_collection).document(uid)
        doc = doc_ref.get()

        if doc.exists:
            doc_ref.delete()
            logger.info(f"Deleted user document for UID: {uid}")
            return True
        else:
            logger.warning(f"User document not found for UID: {uid}")
            return False

    # Search operations
    def create_search(self, search_id: str, user_id: str, timestamp: str,
                     membership_tier: MembershipTier, coordinates: list) -> Dict[str, Any]:
        """
        Create a new search document for a user

        Args:
            search_id: Unique search ID from frontend
            user_id: Firebase user ID
            timestamp: ISO timestamp from frontend
            membership_tier: User's membership tier
            coordinates: List of coordinate/weather data

        Returns:
            dict: Created search document with server timestamps
        """
        doc_ref = self.db.collection(self.searches_collection).document(search_id)

        now = datetime.now(timezone.utc)
        search_data = {
            'id': search_id,
            'userId': user_id,
            'timestamp': timestamp,
            'createdAt': now,
            'updatedAt': now,
            'membershipTier': membership_tier,
            'coordinates': coordinates
        }

        doc_ref.set(search_data)
        logger.info(f"Created search {search_id} for user {user_id}")
        return search_data

    def get_search(self, search_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a search document by ID

        Args:
            search_id: Search document ID

        Returns:
            dict or None: Search document if exists
        """
        doc_ref = self.db.collection(self.searches_collection).document(search_id)
        doc = doc_ref.get()

        if doc.exists:
            return doc.to_dict()
        return None

    def get_user_searches(self, user_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        Get all searches for a user with pagination, sorted by most recent first

        Args:
            user_id: Firebase user ID
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            dict: Contains 'searches', 'total', 'limit', 'offset'
        """
        # Get total count
        all_searches = (
            self.db.collection(self.searches_collection)
            .where(filter=FieldFilter("userId", "==", user_id))
            .stream()
        )
        total = sum(1 for _ in all_searches)

        # Get paginated results, sorted by createdAt descending
        searches_query = (
            self.db.collection(self.searches_collection)
            .where(filter=FieldFilter("userId", "==", user_id))
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .offset(offset)
        )

        searches = [doc.to_dict() for doc in searches_query.stream()]

        return {
            'searches': searches,
            'total': total,
            'limit': limit,
            'offset': offset
        }

    def delete_search(self, search_id: str) -> bool:
        """
        Delete a single search document

        Args:
            search_id: Search document ID

        Returns:
            bool: True if deletion successful, False if search not found
        """
        doc_ref = self.db.collection(self.searches_collection).document(search_id)
        doc = doc_ref.get()

        if doc.exists:
            doc_ref.delete()
            logger.info(f"Deleted search: {search_id}")
            return True
        else:
            logger.warning(f"Search not found: {search_id}")
            return False

    def delete_user_searches(self, user_id: str) -> int:
        """
        Delete all searches for a user

        Args:
            user_id: Firebase user ID

        Returns:
            int: Number of searches deleted
        """
        searches = (
            self.db.collection(self.searches_collection)
            .where(filter=FieldFilter("userId", "==", user_id))
            .stream()
        )

        deleted_count = 0
        for doc in searches:
            doc.reference.delete()
            deleted_count += 1

        logger.info(f"Deleted {deleted_count} searches for user {user_id}")
        return deleted_count

    # Utility methods
    def cleanup_expired_documents(self) -> None:
        """Clean up expired documents across all collections"""
        now = datetime.now(timezone.utc)

        collections = [
            self.coordinates_collection,
            self.gridpoints_collection,
            self.forecasts_collection,
            self.alerts_collection
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
                logger.debug(f"Deleted expired document: {doc.id} from {collection_name}")

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

def delete_user(uid: str) -> bool:
    return firestore_service.delete_user(uid)

# Search convenience functions
def create_search(search_id: str, user_id: str, timestamp: str,
                 membership_tier: MembershipTier, coordinates: list) -> Dict[str, Any]:
    return firestore_service.create_search(search_id, user_id, timestamp, membership_tier, coordinates)

def get_search(search_id: str) -> Optional[Dict[str, Any]]:
    return firestore_service.get_search(search_id)

def get_user_searches(user_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    return firestore_service.get_user_searches(user_id, limit, offset)

def delete_search(search_id: str) -> bool:
    return firestore_service.delete_search(search_id)

def delete_user_searches(user_id: str) -> int:
    return firestore_service.delete_user_searches(user_id)

# Alerts convenience functions
def get_alerts(latitude: str, longitude: str) -> Optional[list]:
    return firestore_service.get_alerts(latitude, longitude)

def set_alerts(latitude: str, longitude: str, alerts: list, expires_at: datetime) -> None:
    return firestore_service.set_alerts(latitude, longitude, alerts, expires_at)