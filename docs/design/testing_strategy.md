# 测试策略

> 配套文档：智能体管理系统构建计划书 v1.7 — 第9章

---

## 1. 测试金字塔

```
        /\
       /E2E\
      /------\
     / 集成测试 \
    /------------\
   /   单元测试    \
  /----------------\
 /  代码静态检查    \
/--------------------\
```

| 层级 | 技术 | 目标覆盖率 | 运行频率 |
|------|------|-----------|---------|
| 静态检查 | Ruff / mypy / ESLint | 100% | 每次提交 |
| 单元测试 | pytest / Vitest | ≥80% | 每次提交 |
| 集成测试 | pytest + Docker | ≥60% | 每次 PR |
| E2E 测试 | Playwright | 核心流程 | 每次发布 |

---

## 2. 后端测试

### 2.1 测试框架

```bash
# pytest + pytest-asyncio + httpx.AsyncClient
# 测试数据库：使用独立测试数据库（test_agent_mgmt）
# Fixture 自动创建/销毁

pip install pytest pytest-asyncio pytest-cov httpx
```

### 2.2 单元测试目录

```
tests/
├── conftest.py                     # 全局 fixtures
├── test_api/                       # API 测试
│   ├── test_auth.py                # 认证测试
│   ├── test_agents.py              # Agent CRUD
│   ├── test_model_templates.py     # 模型模板
│   ├── test_skills.py              # Skill 管理
│   ├── test_mcps.py                # MCP 管理
│   ├── test_chat.py                # 对话接口
│   ├── test_collaboration.py       # 协作
│   └── test_market.py              # 市场
├── test_services/                  # 服务层测试
│   ├── test_agent_service.py
│   ├── test_model_template_service.py
│   ├── test_model_binding_service.py
│   └── test_sync_service.py
├── test_engine/                    # 引擎测试
│   ├── test_agent_engine.py
│   ├── test_collaboration_engine.py
│   └── test_skill_runner.py
└── test_core/                      # 基础设施测试
    ├── test_security.py
    └── test_event_bus.py
```

### 2.3 单元测试示例

```python
# test_model_template_service.py
async def test_create_template(db_session):
    """创建模型配置模板"""
    template = await model_template_service.create_template(
        workspace_id=TEST_WS_ID,
        name="GPT-4o 测试模板",
        provider="openai",
        model_name="gpt-4o",
        api_base_url="https://api.openai.com/v1",
        created_by=TEST_USER_ID
    )
    assert template.name == "GPT-4o 测试模板"
    assert template.version == 1
    assert template.status == "draft"

async def test_bind_agent_to_template(db_session):
    """Agent 绑定模板"""
    binding = await model_template_service.bind_agent(
        template_id=TEMPLATE_ID,
        agent_id=AGENT_ID,
        override_params={"temperature": 0.1}
    )
    assert binding.template_id == TEMPLATE_ID
    assert binding.binding_status == "synced"

async def test_template_update_triggers_sync(db_session):
    """更新模板应标记绑定的 Agent 为 outdated"""
    await model_template_service.update_template(
        template_id=TEMPLATE_ID,
        updates={"model_name": "gpt-4o-mini"}
    )
    bindings = await model_template_service.get_bindings(TEMPLATE_ID)
    assert all(b.binding_status == "outdated" for b in bindings)
```

### 2.4 API 测试示例

```python
# test_model_templates.py
async def test_list_templates(client, auth_header):
    """获取模板列表"""
    resp = await client.get(
        f"/api/v1/workspaces/{WS_ID}/model-templates",
        headers=auth_header
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data["data"]

async def test_create_template_without_auth(client):
    """未认证创建模板应返回 401"""
    resp = await client.post(
        f"/api/v1/workspaces/{WS_ID}/model-templates",
        json={"name": "test", "provider": "openai", "model_name": "gpt-4o"}
    )
    assert resp.status_code == 401
```

---

## 3. 前端测试

### 3.1 测试框架

```bash
# Vitest + React Testing Library + MSW (Mock Service Worker)
pnpm add -D vitest @testing-library/react msw
```

### 3.2 测试目录

```
src/
├── __tests__/
│   ├── components/
│   │   ├── ModelBindingSelect.test.tsx
│   │   ├── TemplateForm.test.tsx
│   │   ├── AgentForm.test.tsx
│   │   └── VersionTimeline.test.tsx
│   ├── pages/
│   │   ├── ModelTemplateList.test.tsx
│   │   ├── ModelTemplateCreate.test.tsx
│   │   └── ModelTemplateDetail.test.tsx
│   ├── stores/
│   │   ├── modelTemplateStore.test.ts
│   │   └── agentStore.test.ts
│   └── services/
│       ├── modelTemplateApi.test.ts
│       └── agentApi.test.ts
```

### 3.3 组件测试示例

```typescript
// ModelBindingSelect.test.tsx
describe('ModelBindingSelect', () => {
  it('应该列出可用的模型模板', async () => {
    render(<ModelBindingSelect workspaceId="test-ws" />);
    expect(screen.getByText('GPT-4o 对话模板')).toBeInTheDocument();
    expect(screen.getByText('DeepSeek V3 本地')).toBeInTheDocument();
  });

  it('选择模板后应触发 onChange', async () => {
    const onChange = vi.fn();
    render(
      <ModelBindingSelect
        workspaceId="test-ws"
        onChange={onChange}
      />
    );
    await userEvent.click(screen.getByText('GPT-4o 对话模板'));
    expect(onChange).toHaveBeenCalledWith('template-uuid');
  });
});
```

---

## 4. E2E 测试（Playwright）

### 4.1 测试场景

| 场景 | 说明 | 优先级 |
|------|------|--------|
| 用户登录流程 | 登录/登出/权限校验 | P0 |
| Agent 创建 + 模型绑定 | 创建 Agent → 选择模型模板 → 验证生效 | P0 |
| 模型模板创建 → 绑定 → 同步 | 创建模板 → 绑定 Agent → 修改 → 自动同步 | P0 |
| 对话流程 | 创建会话 → 发送消息 → 接收回复 | P0 |
| Skill 批量安装 | 选择多个 Agent → 安装 Skill → 验证 | P1 |
| 监控看板 | 查看大盘 → 健康检查 → 告警 | P1 |
| 多 Agent 协作 | 创建协作任务 → 完成 → 查看结果 | P1 |

### 4.2 示例

```typescript
// e2e/model-template.spec.ts
test('创建模型模板 → 绑定 Agent → 修改模板 → 自动同步', async ({ page }) => {
  // 登录
  await page.goto('/login');
  await page.fill('input[name="username"]', 'admin');
  await page.fill('input[name="password"]', 'password');
  await page.click('button[type="submit"]');

  // 进入模型模板页
  await page.click('text=模型配置模板');
  await page.click('text=创建模板');

  // 填写模板信息
  await page.fill('input[name="name"]', 'E2E 测试模板');
  await page.fill('input[name="provider"]', 'openai');
  await page.fill('input[name="modelName"]', 'gpt-4o');
  await page.click('text=测试连接');
  await page.waitForSelector('text=连接成功');
  await page.click('text=保存');

  // 验证模板已创建
  await expect(page.locator('text=E2E 测试模板')).toBeVisible();
});
```

---

## 5. CI/CD 集成

```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]

jobs:
  backend-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_DB: test_agent_mgmt, POSTGRES_PASSWORD: test }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements-dev.txt
      - run: alembic upgrade head
      - run: pytest -v --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v4

  frontend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: pnpm install
      - run: pnpm lint
      - run: pnpm test -- --coverage
      - run: pnpm build
```

---

## 6. 测试数据策略

| 环境 | 数据库 | 数据 | 说明 |
|------|--------|------|------|
| 单元测试 | test_agent_mgmt | Fixture 创建/销毁 | 每次运行前重建 |
| 集成测试 | test_agent_mgmt | 种子数据 | 包含 10 个模板、5 个 Agent |
| E2E 测试 | test_agent_mgmt | 专用测试数据 | Playwright 自动初始化 |
| 开发环境 | agent_mgmt_dev | 开发用种子数据 | 手动运行 seed |

---

> **文件版本：** v1.0 | **更新日期：** 2026-07-26
