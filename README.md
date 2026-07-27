# 本地智能体管理系统 (Local Agent Management System)

一站式本地化智能体管理平台 —— 支持 Agent 创建、Skill 编排、MCP 管理、在线市场、多智能体协作及全链路监控运维。

## 项目结构

```
src/
├── backend/         # FastAPI 后端 (Python 3.11+)
├── frontend/        # React 前端 (TypeScript + Vite)
├── docker/          # Docker Compose 编排文件
└── docs/            # 项目文档
```

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- pnpm

### 启动开发环境

```bash
# 1. 启动基础设施服务 (PostgreSQL, Redis, Qdrant, MinIO)
make infra-up

# 2. 安装后端依赖并启动
make backend-dev

# 3. 安装前端依赖并启动
make frontend-dev

# 4. 访问
# 前端: http://localhost:5173
# 后端: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

## 文档索引

详见 `../plan/` 目录：
- [智能体管理系统构建计划书](../plan/智能体管理系统构建计划书.md)
- [数据库设计](../plan/design/database_design.md)
- [API 接口规范](../plan/design/api_spec.md)
- [架构图看板](../plan/architecture/架构图看板.html)

## 许可

MIT
