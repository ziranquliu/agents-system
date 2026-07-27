# 鏈湴鏅鸿兘浣撶鐞嗙郴缁?(Local Agent Management System)

涓€绔欏紡鏈湴鍖栨櫤鑳戒綋绠＄悊骞冲彴 鈥斺€?鏀寔 Agent 鍒涘缓銆丼kill 缂栨帓銆丮CP 绠＄悊銆佸湪绾垮競鍦恒€佸鏅鸿兘浣撳崗浣滃強鍏ㄩ摼璺洃鎺ц繍缁淬€?
## 椤圭洰缁撴瀯

```
src/
鈹溾攢鈹€ backend/         # FastAPI 鍚庣 (Python 3.11+)
鈹溾攢鈹€ frontend/        # React 鍓嶇 (TypeScript + Vite)
鈹溾攢鈹€ docker/          # Docker Compose 缂栨帓鏂囦欢
鈹斺攢鈹€ docs/            # 椤圭洰鏂囨。
```

## 蹇€熷紑濮?
### 鍓嶇疆瑕佹眰

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- npm

### 鍚姩寮€鍙戠幆澧?
```bash
# 1. 鍚姩鍩虹璁炬柦鏈嶅姟 (PostgreSQL, Redis, Qdrant, MinIO)
make infra-up

# 2. 瀹夎鍚庣渚濊禆骞跺惎鍔?make backend-dev

# 3. 瀹夎鍓嶇渚濊禆骞跺惎鍔?make frontend-dev

# 4. 璁块棶
# 鍓嶇: http://localhost:5173
# 鍚庣: http://localhost:8000
# API 鏂囨。: http://localhost:8000/docs
```

## 鏂囨。绱㈠紩

璇﹁ `../plan/` 鐩綍锛?- [鏅鸿兘浣撶鐞嗙郴缁熸瀯寤鸿鍒掍功](../plan/鏅鸿兘浣撶鐞嗙郴缁熸瀯寤鸿鍒掍功.md)
- [鏁版嵁搴撹璁(../plan/design/database_design.md)
- [API 鎺ュ彛瑙勮寖](../plan/design/api_spec.md)
- [鏋舵瀯鍥剧湅鏉縘(../plan/architecture/鏋舵瀯鍥剧湅鏉?html)

## 璁稿彲

MIT

