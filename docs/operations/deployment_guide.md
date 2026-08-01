# 部署运维手册

> 文档版本: v1.0  
> 最后更新: 2026-08-01

---

## 一、部署架构

```
┌─────────────────────────────────────────────────────────────┐
│                        负载均衡                             │
│                      (Nginx/LB)                             │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │ Backend │         │ Backend │         │ Backend │
   │  :8000  │         │  :8000  │         │  :8000  │
   └────┬────┘         └────┬────┘         └────┬────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │PostgreSQL│        │  Redis  │         │ Qdrant  │
   │  :5432  │         │  :6379  │         │  :6333  │
   └─────────┘         └─────────┘         └─────────┘
```

---

## 二、生产环境配置

### 2.1 环境变量

```bash
# .env.production
DATABASE_URL=postgresql+asyncpg://user:pass@db-host:5432/agent_system
REDIS_URL=redis://redis-host:6379/0
QDRANT_URL=http://qdrant-host:6333

# 安全相关
SECRET_KEY=<生成强随机密钥>
ENCRYPTION_SECRET_KEY=<32位以上加密密钥>
CSRF_SECRET_KEY=<随机密钥>

# 日志级别
LOG_LEVEL=WARNING
```

### 2.2 Docker Compose生产配置

```yaml
# docker/docker-compose.prod.yml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
      - qdrant
    restart: always
    networks:
      - app-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - backend
    restart: always
    networks:
      - app-network

networks:
  app-network:
    driver: bridge
```

---

## 三、启动流程

### 3.1 一键部署脚本

```bash
#!/bin/bash
# scripts/deploy.sh

set -e

echo "=== 开始部署 ==="

# 1. 拉取最新代码
git pull origin main

# 2. 安装依赖
cd backend
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 执行迁移
alembic upgrade head

# 4. 构建前端
cd ../frontend
npm run build

# 5. 重启服务
docker compose -f docker/docker-compose.prod.yml restart

echo "=== 部署完成 ==="
```

### 3.2 健康检查

```bash
# 后端健康检查
curl http://localhost:8000/health

# 预期响应
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "qdrant": "connected",
  "timestamp": "2026-08-01T10:00:00Z"
}
```

---

## 四、监控与告警

### 4.1 Prometheus指标

```python
# backend/app/core/metrics.py
from prometheus_client import Counter, Histogram, generate_latest

request_count = Counter('http_requests_total', 'Total requests', ['method', 'endpoint'])
request_latency = Histogram('http_request_latency_seconds', 'Request latency')

@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    
    request_count.labels(
        method=request.method,
        endpoint=request.url.path
    ).inc()
    
    request_latency.observe(elapsed)
    return response
```

### 4.2 关键监控指标

| 指标 | 阈值 | 告警级别 |
|------|------|---------|
| API响应时间P99 | >500ms | Warning |
| 错误率 | >1% | Critical |
| 数据库连接数 | >80% | Warning |
| Redis内存使用 | >80% | Warning |
| QPS | 超过容量90% | Critical |

---

## 五、备份策略

### 5.1 数据库备份

```bash
#!/bin/bash
# scripts/backup.sh

BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="agent_system"

# 全量备份
pg_dump -U agent -d $DB_NAME > $BACKUP_DIR/full_$DATE.sql

# 压缩备份
gzip $BACKUP_DIR/full_$DATE.sql

# 清理30天前的备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

### 5.2 配置备份

```bash
# 备份配置文件
tar czf /backups/config_$(date +%Y%m%d).tar.gz \
    backend/.env \
    docker/docker-compose.prod.yml \
    nginx/nginx.conf
```

---

## 六、故障排查

### 6.1 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 数据库连接失败 | 服务未启动/网络问题 | 检查PostgreSQL状态 |
| Redis超时 | 内存不足/连接数满 | 清理Redis或增加内存 |
| 前端白屏 | 构建失败/静态资源路径 | 检查构建日志 |
| 403错误 | CSRF Token无效 | 清除Cookie重新登录 |

### 6.2 日志查看

```bash
# Docker日志
docker logs -f agent-system-backend-1

# 应用日志
tail -f logs/app.log

# 错误日志
tail -f logs/error.log
```

---

## 七、扩容指南

### 7.1 水平扩容

```yaml
# docker-compose.prod.yml
backend:
  deploy:
    replicas: 3  # 增加到3个实例
```

### 7.2 数据库读写分离

```python
# 主库写，从库读
from app.db.session import get_write_db, get_read_db

async def read_operation(db=Depends(get_read_db)):
    ...

async def write_operation(db=Depends(get_write_db)):
    ...
```

---

## 八、安全检查清单

- [ ] SSL证书已配置
- [ ] 强密码策略已启用
- [ ] 定期备份任务已设置
- [ ] 监控告警已配置
- [ ] 防火墙规则已设置
- [ ] 敏感信息已从代码中移除
