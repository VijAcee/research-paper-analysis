import sys
import os
from pathlib import Path

# Add app to sys.path
app_dir = Path(__file__).resolve().parent.parent / "app"
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_check():
    """Verify that the health check endpoint is online and reachable."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "online"

def test_register_and_login_flow():
    """Test user registration and subsequent valid login."""
    test_email = "testuser_clean_auth@example.com"
    test_password = "SecurePassword123!"

    # 1. Register user
    reg_response = client.post(
        "/api/auth/register",
        json={"email": test_email, "password": test_password, "full_name": "Test User"}
    )
    assert reg_response.status_code in [200, 400]

    # 2. Valid Login
    login_response = client.post(
        "/api/auth/login",
        json={"email": test_email, "password": test_password}
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert "access_token" in login_data
    assert "token_type" in login_data
    assert login_data.get("user", {}).get("email") == test_email

def test_invalid_email_login():
    """Verify that login with non-existent email returns 401 Unauthorized with detail message."""
    response = client.post(
        "/api/auth/login",
        json={"email": "nonexistent_clean_user@example.com", "password": "SomePassword123!"}
    )
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "No account found" in data["detail"]

def test_invalid_password_login():
    """Verify that login with correct email but wrong password returns 401 Unauthorized with detail message."""
    test_email = "testuser_wrongpwd_clean@example.com"

    # Register first
    client.post(
        "/api/auth/register",
        json={"email": test_email, "password": "CorrectPassword123!"}
    )

    # Attempt login with wrong password
    response = client.post(
        "/api/auth/login",
        json={"email": test_email, "password": "WrongPassword123!"}
    )
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "Incorrect password" in data["detail"]

def test_change_password_validation():
    """Verify change-password succeeds with correct current_password and fails with wrong current_password."""
    test_email = "testuser_changepwd@example.com"
    initial_pwd = "InitialPassword123!"
    new_pwd = "NewSecurePassword123!"

    # 1. Register & Login
    client.post("/api/auth/register", json={"email": test_email, "password": initial_pwd, "full_name": "ChangePwd User"})
    login_res = client.post("/api/auth/login", json={"email": test_email, "password": initial_pwd})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Attempt change-password with INCORRECT current password -> MUST FAIL
    bad_res = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "WrongCurrentPassword123!", "new_password": new_pwd}
    )
    assert bad_res.status_code == 400
    assert "Current password is incorrect" in bad_res.json()["detail"]

    # Verify initial password still works for login
    login_check = client.post("/api/auth/login", json={"email": test_email, "password": initial_pwd})
    assert login_check.status_code == 200

    # 3. Attempt change-password with CORRECT current password -> MUST SUCCEED
    good_res = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": initial_pwd, "new_password": new_pwd}
    )
    assert good_res.status_code == 200

    # Verify new password now works for login
    login_new = client.post("/api/auth/login", json={"email": test_email, "password": new_pwd})
    assert login_new.status_code == 200

def test_logout_and_logout_all():
    """Verify normal logout and logout-all endpoints."""
    test_email = "testuser_logout@example.com"
    pwd = "Password123!"

    client.post("/api/auth/register", json={"email": test_email, "password": pwd})
    login_res = client.post("/api/auth/login", json={"email": test_email, "password": pwd})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout_res = client.post("/api/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    logout_all_res = client.post("/api/auth/logout-all", headers=headers)
    assert logout_all_res.status_code == 200
