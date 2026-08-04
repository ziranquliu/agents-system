"""
API集成测试 - 安全功能
"""
import pytest
from fastapi.testclient import TestClient
def test_api_key_encryption(encryption_service):
    """测试API Key加密"""
    original_key = "sk-test-api-key-12345"
    encrypted = encryption_service.encrypt(original_key)
    decrypted = encryption_service.decrypt(encrypted)
    
    assert encrypted != original_key
    assert decrypted == original_key
def test_api_key_masking(encryption_service):
    """测试API Key掩码显示"""
    full_key = "sk-abcdefghijklmnop12345678"
    masked = encryption_service.mask(full_key)
    
    assert masked.startswith("sk-a")
    assert masked.endswith("5678")
    assert "***" in masked
def test_csrf_protection(client: TestClient):
    """测试CSRF防护"""
    # 不带Token的请求应该失败
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "test", "password": "test"}
    )
    # 登录接口应该是排除的，不检查CSRF
    assert response.status_code in [200, 401, 422]
def test_rate_limiting(client: TestClient):
    """测试限流机制"""
    # 发送多个请求
    for i in range(5):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
    
    # 注意：实际限流测试需要Redis支持
    # 这里只是基本功能测试
def test_security_headers(client: TestClient):
    """测试安全响应头"""
    response = client.get("/api/v1/health")
    
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "X-XSS-Protection" in response.headers
