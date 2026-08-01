"""
性能压测脚本
使用 locust 进行负载测试
"""
from locust import HttpUser, task, between
import json


class AgentSystemUser(HttpUser):
    """性能测试用户"""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """登录获取token"""
        self.client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
    
    @task(3)
    def list_agents(self):
        """列出Agent"""
        self.client.get("/api/v1/agents")
    
    @task(2)
    def get_agent_detail(self):
        """获取Agent详情"""
        self.client.get("/api/v1/agents/test-agent-001")
    
    @task(2)
    def list_conversations(self):
        """列出对话"""
        self.client.get("/api/v1/conversations")
    
    @task(1)
    def stream_chat(self):
        """流式对话（非真实WebSocket，测试接口可用性）"""
        response = self.client.post(
            "/api/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "你好"}],
                "stream": True
            }
        )
    
    @task(1)
    def list_templates(self):
        """列出模型模板"""
        self.client.get("/api/v1/models")
    
    @task(1)
    def health_check(self):
        """健康检查"""
        self.client.get("/health")


class LoadTestUser(HttpUser):
    """压力测试用户 - 并发请求"""
    
    wait_time = between(0, 0.5)
    
    @task
    def stress_test(self):
        """压力测试"""
        with self.client.get("/api/v1/agents", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Got status code {resp.status_code}")


# 运行命令
# locust -f tests/load_test.py --host=http://localhost:8000 --users 100 --spawn-rate 10 --run-time 1m
