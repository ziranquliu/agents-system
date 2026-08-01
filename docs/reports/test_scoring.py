import sys
sys.path.insert(0, r'D:\智能体管理\agents-system\backend')

# 直接测试评分公式（不依赖 DB）
from app.models.health import HealthScoreWeight
from app.services.health_service import HealthScoringService

tpl = HealthScoreWeight(
    template_name='test',
    weight_response_time=30.0,
    weight_token=20.0,
    weight_error_rate=25.0,
    weight_session_success=15.0,
    weight_dependency=10.0,
)

# Case 1: 全部健康 -> 100 分
s, d = HealthScoringService.calculate_score(500, 0.8, 0.001, 0.99, True, tpl)
print(f'Case1 healthy: score={s}, deductions={d["deductions"]}')
assert s == 100.0, f'expected 100, got {s}'

# Case 2: P95=8s, token=1.4, error=3%, session=90%, dep=False
s2, d2 = HealthScoringService.calculate_score(8000, 1.4, 0.03, 0.90, False, tpl)
print(f'Case2 degraded: score={s2}, deductions={d2["deductions"]}')
assert s2 < 100 and s2 > 0, f'unexpected {s2}'

# Case 3: 全部临界 -> 低分
s3, d3 = HealthScoringService.calculate_score(15000, 2.0, 0.10, 0.50, False, tpl)
print(f'Case3 critical: score={s3}, deductions={d3["deductions"]}')
assert s3 <= 25, f'expected <=25, got {s3}'

# Case 4: 权重占比验证 - 响应时间满分时只有响应扣分 20 分 * 30% = 6 分
s4, d4 = HealthScoringService.calculate_score(12000, 0.8, 0.001, 0.99, True, tpl)
print(f'Case4 response-only: score={s4}, resp_deduction={d4["deductions"]["response_time"]}')
assert s4 == 94.0, f'expected 94.0 (100 - 20*0.3), got {s4}'

print('\nALL SCORING TESTS PASSED')
