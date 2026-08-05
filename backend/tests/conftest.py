"""
测试配置 - conftest.py

测试套件使用同步 TestClient + smart mock DB。
SmartMockSession 追踪 db.add() 的对象，在 db.execute() 时根据查询条件返回结果。

依赖覆盖：
1. get_db → SmartMockSession
2. get_current_user → 返回 mock User（避免 JWT + DB 查询链）
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any, Dict, List, Optional
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.main import app
from app.db.session import get_db
from app.services.auth_service import get_current_user


class SmartMockResult:
    """模拟 SQLAlchemy Result，支持 scalar()、scalar_one_or_none()、scalars().all()"""

    def __init__(self, single: Any = None, many: Optional[List] = None):
        self._single = single
        self._many = many or []

    def scalar(self):
        return self._single

    def scalar_one_or_none(self):
        return self._single

    def scalars(self):
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = self._many
        return mock_scalars


class SmartMockSession:
    """追踪 db.add() 对象，在 execute() 时智能返回结果"""

    def __init__(self):
        self._store: Dict[type, List] = {}  # model_class -> [instances]
        self._flush_count = 0

    async def execute(self, stmt):
        """智能分析 select 语句，返回 store 中匹配的结果"""
        if not hasattr(stmt, 'column_descriptions'):
            return SmartMockResult()

        try:
            col_descs = stmt.column_descriptions
            if not col_descs:
                return SmartMockResult()
            entity = col_descs[0].get("entity")
        except Exception:
            return SmartMockResult()

        # 处理 func.count() 查询 — entity 为 None
        if entity is None:
            try:
                # get_final_froms() 替代已废弃的 .froms
                froms = stmt.get_final_froms() if hasattr(stmt, 'get_final_froms') else getattr(stmt, 'froms', [])
                if froms:
                    from_clause = froms[0]
                    # Subquery 有 .element 属性（原始 Select 语句）
                    inner = getattr(from_clause, 'element', None)
                    if inner is not None and hasattr(inner, 'column_descriptions'):
                        inner_descs = inner.column_descriptions
                        if inner_descs:
                            inner_entity = inner_descs[0].get("entity")
                            if inner_entity is not None:
                                store = self._store.get(inner_entity.__name__, [])
                                wc = getattr(inner, 'whereclause', None)
                                if wc is not None:
                                    matches = [o for o in store if self._matches_where(o, wc)]
                                    return SmartMockResult(single=len(matches))
                                return SmartMockResult(single=len(store))
            except Exception:
                pass
            return SmartMockResult(single=0)

        store = self._store.get(entity.__name__, [])

        # 检查是否有 where 条件
        if hasattr(stmt, 'whereclause') and stmt.whereclause is not None:
            # 遍历 store 找到匹配的对象
            matches = []
            for obj in store:
                if self._matches_where(obj, stmt.whereclause):
                    matches.append(obj)
            if matches:
                return SmartMockResult(single=matches[0], many=matches)
            return SmartMockResult(many=[])
        else:
            # 无 where 条件，返回全部
            return SmartMockResult(many=store)

    def _matches_where(self, obj, whereclause):
        """简化匹配：处理 and_/or_ 复合条件、等值、ILIKE"""
        try:
            # 1) 复合条件 (and_ / or_) — BooleanClauseList 带 .clauses 和 .operator
            if hasattr(whereclause, 'clauses') and whereclause.clauses:
                op = str(getattr(whereclause, 'operator', ''))
                results = [self._matches_where(obj, c) for c in whereclause.clauses]
                if 'or' in op.lower():
                    return any(results)
                return all(results)

            # 2) 简单 BinaryExpression (等值 / ilike / like)
            if not hasattr(whereclause, 'left') or not hasattr(whereclause, 'right'):
                return False

            left = whereclause.left
            right = whereclause.right

            if not hasattr(left, 'name'):
                return False

            attr_name = left.name
            actual = getattr(obj, attr_name, None)

            if not hasattr(right, 'value'):
                return False
            expected = right.value

            # 3) ILIKE / LIKE 匹配
            op = str(getattr(whereclause, 'operator', ''))
            if 'ilike' in op.lower() or 'like' in op.lower():
                if actual is None:
                    return False
                pattern = str(expected).replace('%', '')
                return pattern.lower() in str(actual).lower()

            # 4) 等值匹配
            if actual is None and expected is None:
                return True
            if actual is None or expected is None:
                return False
            return actual == expected
        except Exception:
            pass
        return False

    def add(self, instance):
        """追踪添加的对象，同时自动填充 Column default 值"""
        # 自动填充 server_default / default 的列值（模拟 flush 后 DB 填充值）
        self._apply_column_defaults(instance)
        class_name = type(instance).__name__
        if class_name not in self._store:
            self._store[class_name] = []
        self._store[class_name].append(instance)

    def _apply_column_defaults(self, instance):
        """对 ORM 实例中为 None 且有 Python default 的列，自动赋值"""
        try:
            table = getattr(instance, '__table__', None)
            if table is None:
                return
            for col in table.columns:
                current_val = getattr(instance, col.name, None)
                if current_val is None and col.default is not None:
                    try:
                        arg = col.default.arg
                        if callable(arg):
                            try:
                                arg = arg()
                            except TypeError:
                                arg = arg(None)  # SQLAlchemy callable default 可能需要 context
                        setattr(instance, col.name, arg)
                    except Exception:
                        pass
        except Exception:
            pass

    async def get(self, entity, ident):
        """模拟 db.get(Model, primary_key_value)"""
        class_name = entity.__name__
        store = self._store.get(class_name, [])
        pk_attr = getattr(entity, '__table__', None)
        if pk_attr is not None:
            pk_name = pk_attr.primary_key.columns.keys()[0]
        else:
            pk_name = 'id'
        for obj in store:
            if getattr(obj, pk_name, None) == ident:
                return obj
        return None

    async def delete(self, instance):
        """追踪删除的对象"""
        class_name = type(instance).__name__
        store = self._store.get(class_name, [])
        if instance in store:
            store.remove(instance)

    async def flush(self, *args, **kwargs):
        self._flush_count += 1

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def close(self):
        pass

    async def refresh(self, instance, attribute_names=None):
        pass

    def __await__(self):
        return self._async().__await__()

    async def _async(self):
        return self


def _make_mock_result(scalar_result=None, scalars_result=None):
    """向后兼容的 mock Result 构造器"""
    return SmartMockResult(single=scalar_result, many=scalars_result)


@pytest.fixture
def db_session():
    """创建 SmartMockSession"""
    return SmartMockSession()


@pytest.fixture
def mock_user():
    """构造 mock User 对象"""
    user = MagicMock()
    user.id = "test-user-001"
    user.username = "tester"
    user.email = "tester@test.com"
    user.role = "admin"
    user.is_active = True
    user.workspace_id = "ws-test-001"
    return user


@pytest.fixture
def auth_dependency(mock_user):
    """覆盖 get_current_user 依赖，返回 mock User"""
    async def _get_current_user():
        return mock_user
    return _get_current_user


@pytest.fixture
def client(db_session, auth_dependency):
    """创建测试客户端（覆盖 DB + 鉴权依赖）"""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = auth_dependency
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(db_session, auth_dependency):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = auth_dependency
    c = TestClient(app, raise_server_exceptions=False)
    c.headers["Authorization"] = "Bearer admin_token"
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def editor_client(db_session, auth_dependency):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = auth_dependency
    c = TestClient(app, raise_server_exceptions=False)
    c.headers["Authorization"] = "Bearer editor_token"
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def viewer_client(db_session, auth_dependency):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = auth_dependency
    c = TestClient(app, raise_server_exceptions=False)
    c.headers["Authorization"] = "Bearer viewer_token"
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """默认认证头"""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def encryption_service():
    from app.core.encryption import EncryptionHelper
    return EncryptionHelper()


@pytest.fixture
def cache_manager():
    from app.core.cache import CacheManager
    return CacheManager()


@pytest.fixture
def sample_agent():
    return {
        "name": "测试Agent",
        "description": "这是一个测试用的Agent",
        "system_prompt": "你是一个助手",
        "model_provider": "openai",
        "model_name": "gpt-4",
        "workspace_id": "ws-test-001"
    }


@pytest.fixture
def sample_template():
    return {
        "name": "GPT-4 模型模板",
        "provider": "openai",
        "model_name": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 2048,
        "is_default": False
    }


@pytest.fixture
def sample_conversation():
    return {
        "title": "测试对话",
        "agent_id": "agent-001",
        "user_id": "user-001",
        "workspace_id": "ws-test-001"
    }
