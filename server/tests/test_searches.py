from fastapi.testclient import TestClient
from server.main import app
from server.app.auth import get_authenticated_user
from server.app.firestore_service import delete_user_searches
from datetime import datetime, timezone
import uuid


# Mock users with different membership tiers
def mock_free_user():
    return {
        "uid": "test_free_user",
        "email": "free@example.com",
        "membershipTier": "free"
    }


def mock_plus_user():
    return {
        "uid": "test_plus_user",
        "email": "plus@example.com",
        "membershipTier": "plus"
    }


def mock_pro_user():
    return {
        "uid": "test_pro_user",
        "email": "pro@example.com",
        "membershipTier": "pro"
    }


def mock_other_plus_user():
    """Different plus user to test ownership validation"""
    return {
        "uid": "test_other_plus_user",
        "email": "otherplus@example.com",
        "membershipTier": "plus"
    }


client = TestClient(app)
HEADERS = {"Content-Type": "application/json"}
CURRENT_TIME = datetime.now(timezone.utc).isoformat()


def create_test_search_data(search_id=None):
    """Helper to create valid search data"""
    if search_id is None:
        search_id = f"test-search-{uuid.uuid4()}"

    return {
        "id": search_id,
        "timestamp": CURRENT_TIME,
        "coordinates": [
            {
                "key": "37.4258:-122.0987",
                "latitude": "37.4258",
                "longitude": "-122.0987",
                "address": "Mountain View, CA",
                "elevation": "100m",
                "periods": [
                    {"name": "This Afternoon", "temperature": 72, "shortForecast": "Sunny"}
                ],
                "summary": {"maxTemp": 72, "minTemp": 65}
            }
        ]
    }


# Test POST /searches/ - Create search
def test_create_search_as_plus_user():
    """Plus tier user can create a search"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    data = create_test_search_data()
    response = client.post("/searches/", headers=HEADERS, json=data)

    assert response.status_code == 200
    result = response.json()
    assert result["id"] == data["id"]
    assert result["userId"] == "test_plus_user"
    assert result["membershipTier"] == "plus"
    assert "createdAt" in result
    assert "updatedAt" in result
    assert len(result["coordinates"]) == 1

    # Cleanup
    delete_user_searches("test_plus_user")


def test_create_search_as_pro_user():
    """Pro tier user can create a search"""
    client.app.dependency_overrides[get_authenticated_user] = mock_pro_user

    data = create_test_search_data()
    response = client.post("/searches/", headers=HEADERS, json=data)

    assert response.status_code == 200
    result = response.json()
    assert result["userId"] == "test_pro_user"
    assert result["membershipTier"] == "pro"

    # Cleanup
    delete_user_searches("test_pro_user")


def test_create_search_as_free_user():
    """Free tier user cannot create a search (403 Forbidden)"""
    client.app.dependency_overrides[get_authenticated_user] = mock_free_user

    data = create_test_search_data()
    response = client.post("/searches/", headers=HEADERS, json=data)

    assert response.status_code == 403
    result = response.json()
    assert "message" in result["detail"]
    assert "plus" in result["detail"]["message"].lower()


def test_create_search_invalid_id():
    """Search ID must be alphanumeric with hyphens/underscores"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    data = create_test_search_data("invalid@search#id!")
    response = client.post("/searches/", headers=HEADERS, json=data)

    assert response.status_code == 422  # Validation error


def test_create_search_invalid_timestamp():
    """Timestamp must be valid ISO format"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    data = create_test_search_data()
    data["timestamp"] = "not-a-valid-timestamp"
    response = client.post("/searches/", headers=HEADERS, json=data)

    assert response.status_code == 422


def test_create_search_minimal_format():
    """Plus user can create search with minimal format (coordinates only)"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    # Minimal format: coordinates only, no periods/summary/elevation
    data = {
        "id": f"test-search-minimal-{uuid.uuid4()}",
        "timestamp": CURRENT_TIME,
        "coordinates": [
            {
                "key": "37.7749:-122.4194",
                "latitude": "37.7749",
                "longitude": "-122.4194",
                "address": "San Francisco, CA"
                # No elevation, periods, summary
            }
        ]
    }
    response = client.post("/searches/", headers=HEADERS, json=data)

    assert response.status_code == 200
    result = response.json()
    assert result["id"] == data["id"]
    assert result["userId"] == "test_plus_user"
    assert len(result["coordinates"]) == 1
    assert result["coordinates"][0]["latitude"] == "37.7749"
    assert result["coordinates"][0]["longitude"] == "-122.4194"
    assert result["coordinates"][0]["address"] == "San Francisco, CA"

    # Cleanup
    delete_user_searches("test_plus_user")


def test_create_search_full_format_still_works():
    """Verify backward compatibility - full format with periods/summary still works"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    # Full format with all fields
    data = create_test_search_data()  # This includes elevation, periods, summary
    response = client.post("/searches/", headers=HEADERS, json=data)

    assert response.status_code == 200
    result = response.json()
    assert result["id"] == data["id"]
    assert len(result["coordinates"]) == 1
    # Verify all fields are preserved
    coord = result["coordinates"][0]
    assert coord["elevation"] == "100m"
    assert len(coord["periods"]) == 1
    assert coord["summary"]["maxTemp"] == 72

    # Cleanup
    delete_user_searches("test_plus_user")


def test_create_search_mixed_formats():
    """Test creating search with mix of minimal and full coordinates"""
    client.app.dependency_overrides[get_authenticated_user] = mock_pro_user

    data = {
        "id": f"test-search-mixed-{uuid.uuid4()}",
        "timestamp": CURRENT_TIME,
        "coordinates": [
            {
                # Full format
                "key": "37.4258:-122.0987",
                "latitude": "37.4258",
                "longitude": "-122.0987",
                "address": "Mountain View, CA",
                "elevation": "100m",
                "periods": [{"name": "This Afternoon", "temperature": 72}],
                "summary": {"maxTemp": 72, "minTemp": 65}
            },
            {
                # Minimal format
                "key": "37.7749:-122.4194",
                "latitude": "37.7749",
                "longitude": "-122.4194",
                "address": "San Francisco, CA"
                # No elevation, periods, summary
            }
        ]
    }
    response = client.post("/searches/", headers=HEADERS, json=data)

    assert response.status_code == 200
    result = response.json()
    assert len(result["coordinates"]) == 2

    # Cleanup
    delete_user_searches("test_pro_user")


def test_create_search_empty_coordinates():
    """Coordinates list cannot be empty"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    data = create_test_search_data()
    data["coordinates"] = []
    response = client.post("/searches/", headers=HEADERS, json=data)

    assert response.status_code == 422


def test_create_search_invalid_coordinate_key():
    """Coordinate key must be in lat:lng format"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    data = create_test_search_data()
    data["coordinates"][0]["key"] = "invalid_key_format"
    response = client.post("/searches/", headers=HEADERS, json=data)

    assert response.status_code == 422


# Test GET /searches/ - List searches
def test_get_searches_as_plus_user():
    """Plus tier user can retrieve their searches"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    # Create a search first
    search_data = create_test_search_data()
    create_response = client.post("/searches/", headers=HEADERS, json=search_data)
    assert create_response.status_code == 200

    # Get searches
    response = client.get("/searches/", headers=HEADERS)

    assert response.status_code == 200
    result = response.json()
    assert "searches" in result
    assert "total" in result
    assert "limit" in result
    assert "offset" in result
    assert result["total"] >= 1
    assert len(result["searches"]) >= 1

    # Cleanup
    delete_user_searches("test_plus_user")


def test_get_searches_pagination():
    """Test pagination with limit and offset"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    # Create multiple searches
    for i in range(3):
        search_data = create_test_search_data(f"test-search-{i}")
        client.post("/searches/", headers=HEADERS, json=search_data)

    # Test limit
    response = client.get("/searches/?limit=2", headers=HEADERS)
    assert response.status_code == 200
    result = response.json()
    assert len(result["searches"]) <= 2
    assert result["limit"] == 2

    # Test offset
    response = client.get("/searches/?offset=1", headers=HEADERS)
    assert response.status_code == 200
    result = response.json()
    assert result["offset"] == 1

    # Cleanup
    delete_user_searches("test_plus_user")


def test_get_searches_invalid_limit():
    """Limit must be between 1 and 200"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    # Test limit too high
    response = client.get("/searches/?limit=500", headers=HEADERS)
    assert response.status_code == 400
    assert "INVALID_LIMIT" in response.json()["detail"]["code"]

    # Test limit too low
    response = client.get("/searches/?limit=0", headers=HEADERS)
    assert response.status_code == 400


def test_get_searches_invalid_offset():
    """Offset must be non-negative"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    response = client.get("/searches/?offset=-1", headers=HEADERS)
    assert response.status_code == 400
    assert "INVALID_OFFSET" in response.json()["detail"]["code"]


def test_get_searches_as_free_user():
    """Free tier user cannot list searches"""
    client.app.dependency_overrides[get_authenticated_user] = mock_free_user

    response = client.get("/searches/", headers=HEADERS)

    assert response.status_code == 403


# Test GET /searches/{search_id} - Get single search
def test_get_single_search_as_owner():
    """User can retrieve their own search"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    # Create a search
    search_data = create_test_search_data("test-single-search")
    create_response = client.post("/searches/", headers=HEADERS, json=search_data)
    assert create_response.status_code == 200

    # Get the search
    response = client.get("/searches/test-single-search", headers=HEADERS)

    assert response.status_code == 200
    result = response.json()
    assert result["id"] == "test-single-search"
    assert result["userId"] == "test_plus_user"

    # Cleanup
    delete_user_searches("test_plus_user")


def test_get_single_search_not_found():
    """404 when search doesn't exist"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    response = client.get("/searches/nonexistent-search-id", headers=HEADERS)

    assert response.status_code == 404
    assert "SEARCH_NOT_FOUND" in response.json()["detail"]["code"]


def test_get_single_search_not_owner():
    """403 when trying to access another user's search"""
    # Create search as one user
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user
    search_data = create_test_search_data("test-ownership-search")
    create_response = client.post("/searches/", headers=HEADERS, json=search_data)
    assert create_response.status_code == 200

    # Try to access as different user
    client.app.dependency_overrides[get_authenticated_user] = mock_other_plus_user
    response = client.get("/searches/test-ownership-search", headers=HEADERS)

    assert response.status_code == 403
    assert "SEARCH_ACCESS_DENIED" in response.json()["detail"]["code"]

    # Cleanup
    delete_user_searches("test_plus_user")


def test_get_single_search_as_free_user():
    """Free tier user cannot get search"""
    client.app.dependency_overrides[get_authenticated_user] = mock_free_user

    response = client.get("/searches/any-search-id", headers=HEADERS)

    assert response.status_code == 403


# Test DELETE /searches/{search_id} - Delete single search
def test_delete_single_search_as_owner():
    """User can delete their own search"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    # Create a search
    search_data = create_test_search_data("test-delete-search")
    create_response = client.post("/searches/", headers=HEADERS, json=search_data)
    assert create_response.status_code == 200

    # Delete the search
    response = client.delete("/searches/test-delete-search", headers=HEADERS)

    assert response.status_code == 204

    # Verify it's deleted
    get_response = client.get("/searches/test-delete-search", headers=HEADERS)
    assert get_response.status_code == 404


def test_delete_single_search_not_found():
    """404 when trying to delete non-existent search"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    response = client.delete("/searches/nonexistent-search", headers=HEADERS)

    assert response.status_code == 404
    assert "SEARCH_NOT_FOUND" in response.json()["detail"]["code"]


def test_delete_single_search_not_owner():
    """403 when trying to delete another user's search"""
    # Create search as one user
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user
    search_data = create_test_search_data("test-delete-ownership")
    create_response = client.post("/searches/", headers=HEADERS, json=search_data)
    assert create_response.status_code == 200

    # Try to delete as different user
    client.app.dependency_overrides[get_authenticated_user] = mock_other_plus_user
    response = client.delete("/searches/test-delete-ownership", headers=HEADERS)

    assert response.status_code == 403
    assert "SEARCH_DELETE_DENIED" in response.json()["detail"]["code"]

    # Cleanup
    delete_user_searches("test_plus_user")


def test_delete_single_search_as_free_user():
    """Free tier user cannot delete search"""
    client.app.dependency_overrides[get_authenticated_user] = mock_free_user

    response = client.delete("/searches/any-search", headers=HEADERS)

    assert response.status_code == 403


# Test DELETE /searches/ - Delete all searches
def test_delete_all_searches():
    """User can delete all their searches"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    # Create multiple searches
    for i in range(3):
        search_data = create_test_search_data(f"test-delete-all-{i}")
        client.post("/searches/", headers=HEADERS, json=search_data)

    # Delete all searches
    response = client.delete("/searches/", headers=HEADERS)

    assert response.status_code == 200
    result = response.json()
    assert "deleted" in result
    assert result["deleted"] == 3

    # Verify all deleted
    get_response = client.get("/searches/", headers=HEADERS)
    assert get_response.status_code == 200
    assert get_response.json()["total"] == 0


def test_delete_all_searches_empty():
    """Deleting when no searches exist returns 0"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    # Ensure clean slate
    delete_user_searches("test_plus_user")

    response = client.delete("/searches/", headers=HEADERS)

    assert response.status_code == 200
    result = response.json()
    assert result["deleted"] == 0


def test_delete_all_searches_as_free_user():
    """Free tier user cannot delete all searches"""
    client.app.dependency_overrides[get_authenticated_user] = mock_free_user

    response = client.delete("/searches/", headers=HEADERS)

    assert response.status_code == 403


def test_delete_all_searches_only_deletes_own():
    """Deleting all searches only affects the user's own searches"""
    # Create searches as first user
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user
    for i in range(2):
        search_data = create_test_search_data(f"user1-search-{i}")
        client.post("/searches/", headers=HEADERS, json=search_data)

    # Create searches as second user
    client.app.dependency_overrides[get_authenticated_user] = mock_other_plus_user
    for i in range(2):
        search_data = create_test_search_data(f"user2-search-{i}")
        client.post("/searches/", headers=HEADERS, json=search_data)

    # First user deletes all their searches
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user
    delete_response = client.delete("/searches/", headers=HEADERS)
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] == 2

    # Second user's searches should still exist
    client.app.dependency_overrides[get_authenticated_user] = mock_other_plus_user
    get_response = client.get("/searches/", headers=HEADERS)
    assert get_response.status_code == 200
    assert get_response.json()["total"] == 2

    # Cleanup
    delete_user_searches("test_other_plus_user")


# Test multiple coordinates
def test_create_search_with_multiple_coordinates():
    """Search can contain multiple coordinates"""
    client.app.dependency_overrides[get_authenticated_user] = mock_plus_user

    data = {
        "id": f"test-multi-coord-{uuid.uuid4()}",
        "timestamp": CURRENT_TIME,
        "coordinates": [
            {
                "key": "37.4258:-122.0987",
                "latitude": "37.4258",
                "longitude": "-122.0987",
                "address": "Mountain View, CA",
                "elevation": "100m",
                "periods": [],
                "summary": {}
            },
            {
                "key": "40.7128:-74.0060",
                "latitude": "40.7128",
                "longitude": "-74.0060",
                "address": "New York, NY",
                "elevation": "10m",
                "periods": [],
                "summary": {}
            }
        ]
    }

    response = client.post("/searches/", headers=HEADERS, json=data)

    assert response.status_code == 200
    result = response.json()
    assert len(result["coordinates"]) == 2

    # Cleanup
    delete_user_searches("test_plus_user")
