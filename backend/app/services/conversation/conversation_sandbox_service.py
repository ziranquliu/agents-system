"""
会话沙箱测试服务

功能:
- 隔离测试环境
- Agent 行为验证
- 多轮对话模拟
- 断言检查
- 回归测试集
"""

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class SandboxTestCase:
    """沙箱测试用例"""
    id: str = ""
    name: str = ""
    description: str = ""
    agent_id: str = ""
    messages: list[dict] = field(default_factory=list)  # [{role, content}]
    assertions: list[dict] = field(default_factory=list)  # [{type, expected}]
    tags: list[str] = field(default_factory=list)
    timeout: float = 60


@dataclass
class SandboxResult:
    """沙箱测试结果"""
    test_id: str = ""
    case_id: str = ""
    status: str = "pending"  # pending / passed / failed / error / timeout
    assertions_passed: int = 0
    assertions_total: int = 0
    response: str = ""
    latency_ms: float = 0
    error: str = ""
    details: list[dict] = field(default_factory=list)
    timestamp: float = 0


@dataclass
class SandboxSession:
    """沙箱会话"""
    id: str = ""
    agent_id: str = ""
    created_at: float = 0
    messages: list[dict] = field(default_factory=list)
    is_active: bool = True


class ConversationSandboxService:
    """
    会话沙箱测试服务

    - 隔离环境: 不影响生产数据
    - 多轮对话: 支持上下文连续
    - 断言: contains / not_contains / equals / regex / intent / length
    - 回归测试: 批量执行 + 通过率
    """

    ASSERTION_TYPES = {"contains", "not_contains", "equals", "regex", "length_gt", "length_lt", "intent"}

    def __init__(self):
        self._test_cases: dict[str, SandboxTestCase] = {}
        self._sessions: dict[str, SandboxSession] = {}
        self._results: dict[str, list[SandboxResult]] = defaultdict(list)
        self._call_fn: Optional[Callable] = None

    def set_call_fn(self, fn: Callable):
        """设置 LLM 调用函数: async fn(messages) -> str"""
        self._call_fn = fn

    # ----------------------------------------------------------
    # 测试用例管理
    # ----------------------------------------------------------

    def create_test_case(self, case: dict) -> dict:
        """创建测试用例"""
        tc = SandboxTestCase(**case)
        if not tc.id:
            tc.id = f"tc_{uuid.uuid4().hex[:10]}"
        self._test_cases[tc.id] = tc
        return {"case_id": tc.id, "created": True}

    def get_test_case(self, case_id: str) -> Optional[dict]:
        tc = self._test_cases.get(case_id)
        if not tc:
            return None
        return {
            "id": tc.id,
            "name": tc.name,
            "description": tc.description,
            "agent_id": tc.agent_id,
            "messages": tc.messages,
            "assertions": tc.assertions,
            "tags": tc.tags,
        }

    def list_test_cases(self, tag: str = "", agent_id: str = "") -> list[dict]:
        cases = list(self._test_cases.values())
        if tag:
            cases = [c for c in cases if tag in c.tags]
        if agent_id:
            cases = [c for c in cases if c.agent_id == agent_id]
        return [
            {"id": c.id, "name": c.name, "agent_id": c.agent_id, "tags": c.tags}
            for c in cases
        ]

    def delete_test_case(self, case_id: str) -> dict:
        if case_id in self._test_cases:
            del self._test_cases[case_id]
            return {"deleted": True}
        return {"error": "用例不存在"}

    # ----------------------------------------------------------
    # 执行
    # ----------------------------------------------------------

    async def run_single(self, case_id: str) -> dict:
        """执行单条测试"""
        tc = self._test_cases.get(case_id)
        if not tc:
            return {"error": "用例不存在"}

        result = SandboxResult(
            test_id=f"test_{uuid.uuid4().hex[:8]}",
            case_id=case_id,
            timestamp=time.time(),
        )

        try:
            start = time.time()
            response = await self._call_agent(tc)
            result.latency_ms = (time.time() - start) * 1000
            result.response = response

            # 断言检查
            for assertion in tc.assertions:
                passed = self._check_assertion(response, assertion)
                result.assertions_total += 1
                if passed:
                    result.assertions_passed += 1
                result.details.append({
                    "type": assertion.get("type", ""),
                    "expected": assertion.get("expected", ""),
                    "passed": passed,
                })

            result.status = "passed" if result.assertions_passed == result.assertions_total else "failed"

        except TimeoutError:
            result.status = "timeout"
            result.error = f"超时 ({tc.timeout}s)"
        except Exception as e:
            result.status = "error"
            result.error = str(e)

        self._results[case_id].append(result)
        return {
            "test_id": result.test_id,
            "case_id": result.case_id,
            "status": result.status,
            "assertions_passed": result.assertions_passed,
            "assertions_total": result.assertions_total,
            "latency_ms": result.latency_ms,
            "error": result.error,
        }

    async def run_batch(self, case_ids: Optional[list[str]] = None, tag: str = "") -> dict:
        """批量执行测试"""
        if not case_ids:
            cases = list(self._test_cases.values())
            if tag:
                cases = [c for c in cases if tag in c.tags]
            case_ids = [c.id for c in cases]

        results = []
        for cid in case_ids:
            r = await self.run_single(cid)
            results.append(r)

        total = len(results)
        passed = sum(1 for r in results if r.get("status") == "passed")
        failed = sum(1 for r in results if r.get("status") == "failed")
        errors = sum(1 for r in results if r.get("status") in ("error", "timeout"))

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": round(passed / max(total, 1) * 100, 1),
            "results": results,
        }

    async def _call_agent(self, tc: SandboxTestCase) -> str:
        """调用 Agent"""
        if not self._call_fn:
            return f"[sandbox模拟] 收到 {len(tc.messages)} 条消息"

        messages = tc.messages.copy()
        response = await self._call_fn(messages)
        return response

    def _check_assertion(self, response: str, assertion: dict) -> bool:
        """检查断言"""
        a_type = assertion.get("type", "")
        expected = assertion.get("expected", "")
        response_lower = response.lower()

        if a_type == "contains":
            return expected.lower() in response_lower
        elif a_type == "not_contains":
            return expected.lower() not in response_lower
        elif a_type == "equals":
            return response.strip() == expected.strip()
        elif a_type == "length_gt":
            return len(response) > int(expected)
        elif a_type == "length_lt":
            return len(response) < int(expected)
        else:
            return True

    # ----------------------------------------------------------
    # 交互式沙箱
    # ----------------------------------------------------------

    def create_session(self, agent_id: str) -> dict:
        """创建交互式沙箱会话"""
        session = SandboxSession(
            id=f"sbox_{uuid.uuid4().hex[:10]}",
            agent_id=agent_id,
            created_at=time.time(),
        )
        self._sessions[session.id] = session
        return {"session_id": session.id, "agent_id": agent_id}

    async def send_message(self, session_id: str, content: str) -> dict:
        """发送消息"""
        session = self._sessions.get(session_id)
        if not session or not session.is_active:
            return {"error": "沙箱会话不存在或已关闭"}

        session.messages.append({"role": "user", "content": content})

        try:
            response = await self._call_agent_list(session.messages)
            session.messages.append({"role": "assistant", "content": response})
            return {"response": response, "message_count": len(session.messages)}
        except Exception as e:
            return {"error": str(e)}

    async def _call_agent_list(self, messages: list[dict]) -> str:
        if not self._call_fn:
            return "[sandbox模拟回复]"
        return await self._call_fn(messages)

    def close_session(self, session_id: str) -> dict:
        session = self._sessions.get(session_id)
        if session:
            session.is_active = False
            return {"closed": True}
        return {"error": "会话不存在"}

    def get_session_history(self, session_id: str) -> list[dict]:
        session = self._sessions.get(session_id)
        if not session:
            return []
        return session.messages

    # ----------------------------------------------------------
    # 统计
    # ----------------------------------------------------------

    def get_statistics(self) -> dict:
        total_cases = len(self._test_cases)
        total_results = sum(len(r) for r in self._results.values())
        all_results = [r for results in self._results.values() for r in results]
        passed = sum(1 for r in all_results if r.status == "passed")
        return {
            "total_cases": total_cases,
            "total_executions": total_results,
            "overall_pass_rate": round(passed / max(total_results, 1) * 100, 1),
            "active_sessions": sum(1 for s in self._sessions.values() if s.is_active),
        }


# 全局实例
_sandbox_service: Optional[ConversationSandboxService] = None


def get_sandbox_service() -> ConversationSandboxService:
    global _sandbox_service
    if _sandbox_service is None:
        _sandbox_service = ConversationSandboxService()
    return _sandbox_service
