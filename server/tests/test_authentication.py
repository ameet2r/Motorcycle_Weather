import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import HTTPException
from firebase_admin import auth
import json

# Import the app and auth components
from ..main import app
from ..app.auth import get_current_user, get_authenticated_user
from ..app.firebase_admin import verify_firebase_token, get_user_info


class TestFirebaseAdmin:
    """Test Firebase Admin SDK functionality"""
    
    @patch('server.app.firebase_admin.firebase_admin.initialize_app')
    @patch('server.app.firebase_admin.credentials.Certificate')
    def test_get_firebase_app_with_service_account(self, mock_cert, mock_init):
        """Test Firebase app initialization with service account"""
        from server.app.firebase_admin import get_firebase_app
        
        # Mock environment variables
        with patch.dict(os.environ, {
            'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/service-account.json',
            'GOOGLE_CLOUD_PROJECT': 'test-project'
        }):
            with patch('os.path.exists', return_value=True):
                mock_app = Mock()
                mock_init.return_value = mock_app
                
                result = get_firebase_app()
                
                mock_cert.assert_called_once_with('/path/to/service-account.json')
                mock_init.assert_called_once()
                assert result == mock_app
    
    @patch('server.app.firebase_admin.auth.verify_id_token')
    @patch('server.app.firebase_admin.get_firebase_app')
    async def test_verify_firebase_token_success(self, mock_get_app, mock_verify):
        """Test successful token verification"""
        mock_app = Mock()
        mock_get_app.return_value = mock_app
        
        mock_decoded_token = {
            'uid': 'test-uid',
            'email': 'test@example.com',
            'email_verified': True
        }
        mock_verify.return_value = mock_decoded_token
        
        result = await verify_firebase_token('valid-token')
        
        mock_verify.assert_called_once_with('valid-token', app=mock_app)
        assert result == mock_decoded_token
    
    @patch('server.app.firebase_admin.auth.verify_id_token')
    @patch('server.app.firebase_admin.get_firebase_app')
    async def test_verify_firebase_token_invalid(self, mock_get_app, mock_verify):
        """Test invalid token verification"""
        mock_app = Mock()
        mock_get_app.return_value = mock_app
        mock_verify.side_effect = auth.InvalidIdTokenError('Invalid token')
        
        with pytest.raises(auth.InvalidIdTokenError):
            await verify_firebase_token('invalid-token')
    
    @patch('server.app.firebase_admin.auth.verify_id_token')
    @patch('server.app.firebase_admin.get_firebase_app')
    async def test_verify_firebase_token_expired(self, mock_get_app, mock_verify):
        """Test expired token verification"""
        mock_app = Mock()
        mock_get_app.return_value = mock_app
        mock_verify.side_effect = auth.ExpiredIdTokenError('Token expired')
        
        with pytest.raises(auth.ExpiredIdTokenError):
            await verify_firebase_token('expired-token')
    
    def test_get_user_info(self):
        """Test user info extraction from decoded token"""
        decoded_token = {
            'uid': 'test-uid',
            'email': 'test@example.com',
            'email_verified': True,
            'name': 'Test User',
            'picture': 'https://example.com/photo.jpg',
            'firebase': {'sign_in_provider': 'google.com'},
            'auth_time': 1640995200,
            'exp': 1641081600,
            'iat': 1640995200
        }
        
        result = get_user_info(decoded_token)
        
        assert result['uid'] == 'test-uid'
        assert result['email'] == 'test@example.com'
        assert result['email_verified'] is True
        assert result['name'] == 'Test User'
        assert result['provider_id'] == 'google.com'


class TestAuthDependencies:
    """Test FastAPI authentication dependencies"""
    
    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request object"""
        request = Mock()
        request.url.path = "/CoordinatesToWeather/"
        return request
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock HTTP Bearer credentials"""
        credentials = Mock()
        credentials.credentials = "valid-token"
        return credentials
    
    @patch('server.app.auth.verify_firebase_token')
    async def test_get_authenticated_user_success(self, mock_verify, mock_request, mock_credentials):
        """Test successful user authentication"""
        mock_decoded_token = {
            'uid': 'test-uid',
            'email': 'test@example.com',
            'email_verified': True
        }
        mock_verify.return_value = mock_decoded_token
        
        result = await get_authenticated_user(mock_request, mock_credentials)
        
        assert result['uid'] == 'test-uid'
        assert result['email'] == 'test@example.com'
    
    async def test_get_authenticated_user_no_credentials(self, mock_request):
        """Test authentication failure with no credentials"""
        with pytest.raises(HTTPException) as exc_info:
            await get_authenticated_user(mock_request, None)
        
        assert exc_info.value.status_code == 401
        assert "AUTH_TOKEN_MISSING" in str(exc_info.value.detail)
    
    @patch('server.app.auth.verify_firebase_token')
    async def test_get_authenticated_user_invalid_token(self, mock_verify, mock_request, mock_credentials):
        """Test authentication failure with invalid token"""
        mock_verify.side_effect = auth.InvalidIdTokenError('Invalid token')
        
        with pytest.raises(HTTPException) as exc_info:
            await get_authenticated_user(mock_request, mock_credentials)
        
        assert exc_info.value.status_code == 401
        assert "AUTH_TOKEN_INVALID" in str(exc_info.value.detail)
    
    @patch('server.app.auth.verify_firebase_token')
    async def test_get_current_user_excluded_path(self, mock_verify):
        """Test that excluded paths skip authentication"""
        request = Mock()
        request.url.path = "/health"
        
        result = await get_current_user(request, None)
        
        assert result is None
        mock_verify.assert_not_called()


class TestEndpointAuthentication:
    """Test authentication on actual endpoints"""
    
    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)
    
    def test_health_endpoint_no_auth_required(self):
        """Test that health endpoint works without authentication"""
        response = self.client.get("/health")
        assert response.status_code == 200
        assert "healthy" in response.json()["status"]
    
    def test_root_endpoint_no_auth_required(self):
        """Test that root endpoint works without authentication"""
        response = self.client.get("/")
        assert response.status_code == 200
        assert "Motorcycle Weather API is running" in response.json()["message"]
    
    def test_coordinates_endpoint_requires_auth(self):
        """Test that CoordinatesToWeather endpoint requires authentication"""
        test_request = {
            "coordinates": [
                {
                    "latLng": {
                        "latitude": "37.7749",
                        "longitude": "-122.4194"
                    }
                }
            ],
            "ignoreEta": False
        }
        
        response = self.client.post("/CoordinatesToWeather/", json=test_request)
        assert response.status_code == 401
        assert "AUTH_TOKEN_MISSING" in str(response.json())
    
    @patch('server.app.auth.verify_firebase_token')
    def test_coordinates_endpoint_with_valid_auth(self, mock_verify):
        """Test CoordinatesToWeather endpoint with valid authentication"""
        # Mock the token verification
        mock_decoded_token = {
            'uid': 'test-uid',
            'email': 'test@example.com',
            'email_verified': True
        }
        mock_verify.return_value = mock_decoded_token
        
        test_request = {
            "coordinates": [
                {
                    "latLng": {
                        "latitude": "37.7749",
                        "longitude": "-122.4194"
                    }
                }
            ],
            "ignoreEta": False
        }
        
        headers = {"Authorization": "Bearer valid-token"}
        
        # Mock the weather service calls to avoid external API calls
        with patch('server.main.getWeather') as mock_get_weather, \
             patch('server.main.filterWeatherData') as mock_filter_weather:
            
            mock_filter_weather.return_value = {"test": "data"}
            
            response = self.client.post("/CoordinatesToWeather/", json=test_request, headers=headers)
            
            # The endpoint should process the request
            assert response.status_code == 200
            result = response.json()
            assert "coordinates_to_forecasts_map" in result
            assert "user_info" in result
            assert result["user_info"]["uid"] == "test-uid"
    
    def test_coordinates_endpoint_with_invalid_auth(self):
        """Test CoordinatesToWeather endpoint with invalid authentication"""
        test_request = {
            "coordinates": [
                {
                    "latLng": {
                        "latitude": "37.7749",
                        "longitude": "-122.4194"
                    }
                }
            ],
            "ignoreEta": False
        }
        
        headers = {"Authorization": "Bearer invalid-token"}
        
        with patch('server.app.auth.verify_firebase_token') as mock_verify:
            mock_verify.side_effect = auth.InvalidIdTokenError('Invalid token')
            
            response = self.client.post("/CoordinatesToWeather/", json=test_request, headers=headers)
            assert response.status_code == 401
            assert "AUTH_TOKEN_INVALID" in str(response.json())


class TestErrorHandling:
    """Test comprehensive error handling scenarios"""
    
    @patch('server.app.auth.verify_firebase_token')
    async def test_expired_token_error(self, mock_verify):
        """Test handling of expired tokens"""
        mock_verify.side_effect = auth.ExpiredIdTokenError('Token expired')
        
        request = Mock()
        request.url.path = "/CoordinatesToWeather/"
        credentials = Mock()
        credentials.credentials = "expired-token"
        
        with pytest.raises(HTTPException) as exc_info:
            await get_authenticated_user(request, credentials)
        
        assert exc_info.value.status_code == 401
        assert "AUTH_TOKEN_EXPIRED" in str(exc_info.value.detail)
    
    @patch('server.app.auth.verify_firebase_token')
    async def test_revoked_token_error(self, mock_verify):
        """Test handling of revoked tokens"""
        mock_verify.side_effect = auth.RevokedIdTokenError('Token revoked')
        
        request = Mock()
        request.url.path = "/CoordinatesToWeather/"
        credentials = Mock()
        credentials.credentials = "revoked-token"
        
        with pytest.raises(HTTPException) as exc_info:
            await get_authenticated_user(request, credentials)
        
        assert exc_info.value.status_code == 401
        assert "AUTH_TOKEN_REVOKED" in str(exc_info.value.detail)
    
    @patch('server.app.auth.verify_firebase_token')
    async def test_malformed_token_error(self, mock_verify):
        """Test handling of malformed tokens"""
        mock_verify.side_effect = ValueError('Invalid token format')
        
        request = Mock()
        request.url.path = "/CoordinatesToWeather/"
        credentials = Mock()
        credentials.credentials = "malformed-token"
        
        with pytest.raises(HTTPException) as exc_info:
            await get_authenticated_user(request, credentials)
        
        assert exc_info.value.status_code == 401
        assert "AUTH_TOKEN_MALFORMED" in str(exc_info.value.detail)
    
    @patch('server.app.auth.verify_firebase_token')
    async def test_internal_auth_error(self, mock_verify):
        """Test handling of unexpected authentication errors"""
        mock_verify.side_effect = Exception('Unexpected error')
        
        request = Mock()
        request.url.path = "/CoordinatesToWeather/"
        credentials = Mock()
        credentials.credentials = "some-token"
        
        with pytest.raises(HTTPException) as exc_info:
            await get_authenticated_user(request, credentials)
        
        assert exc_info.value.status_code == 500
        assert "AUTH_INTERNAL_ERROR" in str(exc_info.value.detail)


if __name__ == "__main__":
    pytest.main([__file__])