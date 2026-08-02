# 修复后端和前端报错

## 问题分析

### 后端报错
```
SyntaxError: invalid syntax (router.py, line 3)
```

**原因**: router.py 文件导入语句格式错误
```python
from app.api.v1 import (
"""API v1 路由聚合 - 最终版本"""
    auth, agents, models, ...
)
```

### 前端报错
```
No matching export in "src/hooks/useWebSocket.ts" for import "useWebSocket"
```

**原因**: useWebSocket.ts 导出的是 `useWebSocketChat`，但 ConversationDetail.tsx 导入的是 `useWebSocket`

---

## 修复方案

### 1. 修复 router.py
需要重写 router.py 文件，修复导入语句格式。

### 2. 修复 useWebSocket.ts
需要在 useWebSocket.ts 中添加 `useWebSocket` 的导出别名。

---

## 执行修复

### 步骤 1: 修复 router.py
```python
# 正确的导入格式
from app.api.v1 import auth, agents, models, chat, conversations, skills, workspaces
# ... 其他导入

api_router = APIRouter()
# ... 路由注册
```

### 步骤 2: 修复 useWebSocket.ts
```typescript
// 添加导出别名
export { useWebSocketChat as useWebSocket } from './useWebSocket'
```

---

## 验证步骤

### 后端验证
```bash
cd backend
python -c "from app.main import app; print('OK')"
python -m uvicorn app.main:app --reload
```

### 前端验证
```bash
cd frontend
npm run dev
```

---

## 状态
- [ ] 修复 router.py
- [ ] 修复 useWebSocket.ts
- [ ] 验证后端启动
- [ ] 验证前端启动
- [ ] 测试 API 端点
