"""Comprehensive feature completion check"""
import sys
import os
from pathlib import Path
from collections import defaultdict
import re

sys.path.insert(0, r'D:\智能体管理\agents-system\backend')
os.chdir(r'D:\智能体管理\agents-system\backend')

output = 'feature_check_result.txt'

with open(output, 'w', encoding='utf-8') as f:
    f.write("=" * 80 + "\n")
    f.write("FEATURE COMPLETION CHECK\n")
    f.write("=" * 80 + "\n\n")
    
    # Load app
    try:
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        f.write("[OK] Application loaded\n\n")
    except Exception as e:
        f.write(f"[FAIL] Application load error: {e}\n\n")
        sys.exit(1)
    
    # ==========================================
    # 1. Core Feature Check
    # ==========================================
    f.write("=" * 80 + "\n")
    f.write("[1] CORE FEATURE COMPLETION CHECK\n")
    f.write("=" * 80 + "\n\n")
    
    # Define expected features and their API endpoints
    features = {
        "Authentication": {
            "endpoints": [
                ("/api/v1/auth/register", "POST"),
                ("/api/v1/auth/login", "POST"),
                ("/api/v1/auth/me", "GET"),
                ("/api/v1/auth/logout", "POST"),
            ],
            "status": "pending"
        },
        "Agent Management": {
            "endpoints": [
                ("/api/v1/agents/", "GET"),
                ("/api/v1/agents/", "POST"),
                ("/api/v1/agents/{agent_id}", "GET"),
                ("/api/v1/agents/{agent_id}", "PUT"),
                ("/api/v1/agents/{agent_id}", "DELETE"),
                ("/api/v1/agents/{agent_id}/status", "PATCH"),
            ],
            "status": "pending"
        },
        "Model Configuration": {
            "endpoints": [
                ("/api/v1/models/", "GET"),
                ("/api/v1/models/", "POST"),
                ("/api/v1/models/{template_id}", "GET"),
                ("/api/v1/models/{template_id}", "PUT"),
                ("/api/v1/models/{template_id}", "DELETE"),
                ("/api/v1/models/{template_id}/test", "POST"),
                ("/api/v1/models/{template_id}/sync-binding-agents", "POST"),
            ],
            "status": "pending"
        },
        "Model Version Management": {
            "endpoints": [
                ("/api/v1/model-templates/", "GET"),
                ("/api/v1/model-templates/{template_id}/versions", "GET"),
                ("/api/v1/model-templates/{template_id}/versions/{version}", "GET"),
                ("/api/v1/model-templates/{template_id}/rollback", "POST"),
                ("/api/v1/model-templates/{template_id}/bound-agents", "GET"),
                ("/api/v1/model-templates/{template_id}/sync", "POST"),
            ],
            "status": "pending"
        },
        "Skill Management": {
            "endpoints": [
                ("/api/v1/skills/", "GET"),
                ("/api/v1/skills/", "POST"),
                ("/api/v1/skills/{skill_id}", "GET"),
                ("/api/v1/skills/{skill_id}", "PUT"),
                ("/api/v1/skills/{skill_id}", "DELETE"),
                ("/api/v1/skills/{skill_id}/toggle", "PATCH"),
                ("/api/v1/skills/{skill_id}/bind", "POST"),
            ],
            "status": "pending"
        },
        "MCP Server Management": {
            "endpoints": [
                ("/api/v1/mcp-servers/", "GET"),
                ("/api/v1/mcp-servers/", "POST"),
                ("/api/v1/mcp-servers/{server_id}", "GET"),
                ("/api/v1/mcp-servers/{server_id}", "PUT"),
                ("/api/v1/mcp-servers/{server_id}", "DELETE"),
                ("/api/v1/mcp-servers/{server_id}/health-check", "POST"),
            ],
            "status": "pending"
        },
        "Conversation Management": {
            "endpoints": [
                ("/api/v1/conversations/", "GET"),
                ("/api/v1/conversations/", "POST"),
                ("/api/v1/conversations/{conversation_id}", "GET"),
                ("/api/v1/conversations/{conversation_id}", "PUT"),
                ("/api/v1/conversations/{conversation_id}", "DELETE"),
                ("/api/v1/conversations/{conversation_id}/messages", "GET"),
                ("/api/v1/conversations/{conversation_id}/messages", "POST"),
            ],
            "status": "pending"
        },
        "Chat Completion": {
            "endpoints": [
                ("/api/v1/chat/completions", "POST"),
                ("/api/v1/chat/embeddings", "POST"),
            ],
            "status": "pending"
        },
        "Workspace Management": {
            "endpoints": [
                ("/api/v1/workspaces/", "GET"),
                ("/api/v1/workspaces/", "POST"),
                ("/api/v1/workspaces/{workspace_id}", "GET"),
                ("/api/v1/workspaces/{workspace_id}", "PUT"),
                ("/api/v1/workspaces/{workspace_id}", "DELETE"),
                ("/api/v1/workspaces/{workspace_id}/members", "GET"),
                ("/api/v1/workspaces/{workspace_id}/members", "POST"),
            ],
            "status": "pending"
        },
        "Memory Management": {
            "endpoints": [
                ("/api/v1/memories", "GET"),
                ("/api/v1/memories/{memory_id}", "GET"),
            ],
            "status": "pending"
        },
        "Token Management": {
            "endpoints": [
                ("/api/v1/tokens/usage", "GET"),
                ("/api/v1/tokens/stats", "GET"),
                ("/api/v1/tokens/budget", "GET"),
                ("/api/v1/tokens/alerts", "GET"),
            ],
            "status": "pending"
        },
        "Health Monitoring": {
            "endpoints": [
                ("/api/v1/health/", "GET"),
                ("/api/v1/health/configs/{agent_id}", "GET"),
            ],
            "status": "pending"
        },
        "Audit Logs": {
            "endpoints": [
                ("/api/v1/audit/logs", "GET"),
                ("/api/v1/audit/stats", "GET"),
                ("/api/v1/audit/rules", "GET"),
            ],
            "status": "pending"
        },
        "Backup & Restore": {
            "endpoints": [
                ("/api/v1/backup-enhanced/backups", "GET"),
                ("/api/v1/backup-enhanced/restores", "GET"),
            ],
            "status": "pending"
        },
        "Collaboration": {
            "endpoints": [
                ("/api/v1/collaborations", "GET"),
                ("/api/v1/collaborations/{collab_id}/tasks", "GET"),
            ],
            "status": "pending"
        },
    }
    
    # Get all registered routes
    all_routes = {}
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            for method in route.methods:
                if method not in ['HEAD', 'OPTIONS']:
                    all_routes[f"{method} {route.path}"] = route
    
    # Check each feature
    f.write("Feature Status Check:\n")
    f.write("-" * 60 + "\n")
    
    completed_features = []
    incomplete_features = []
    
    for feature_name, feature_info in features.items():
        endpoints = feature_info["endpoints"]
        found_endpoints = []
        missing_endpoints = []
        
        for path, method in endpoints:
            route_key = f"{method} {path}"
            if route_key in all_routes:
                found_endpoints.append(route_key)
            else:
                missing_endpoints.append(route_key)
        
        if not missing_endpoints:
            feature_info["status"] = "completed"
            completed_features.append(feature_name)
            f.write(f"[OK] {feature_name}: {len(found_endpoints)}/{len(endpoints)} endpoints\n")
        else:
            feature_info["status"] = "incomplete"
            incomplete_features.append((feature_name, missing_endpoints))
            f.write(f"[WARN] {feature_name}: {len(found_endpoints)}/{len(endpoints)} endpoints\n")
            for ep in missing_endpoints[:3]:
                f.write(f"      Missing: {ep}\n")
            if len(missing_endpoints) > 3:
                f.write(f"      ... and {len(missing_endpoints) - 3} more\n")
    
    f.write("\n" + "=" * 80 + "\n")
    f.write("SUMMARY\n")
    f.write("=" * 80 + "\n\n")
    
    total_features = len(features)
    completed_count = len(completed_features)
    incomplete_count = len(incomplete_features)
    
    f.write(f"Total Features: {total_features}\n")
    f.write(f"Completed: {completed_count}\n")
    f.write(f"Incomplete: {incomplete_count}\n")
    f.write(f"Completion Rate: {completed_count/total_features*100:.1f}%\n\n")
    
    if incomplete_features:
        f.write("Incomplete Features:\n")
        f.write("-" * 60 + "\n")
        for feature, missing in incomplete_features:
            f.write(f"\n{feature}:\n")
            for ep in missing:
                f.write(f"  - {ep}\n")
    
    # ==========================================
    # 2. Service Layer Check
    # ==========================================
    f.write("\n" + "=" * 80 + "\n")
    f.write("[2] SERVICE LAYER COMPLETION CHECK\n")
    f.write("=" * 80 + "\n\n")
    
    services_dir = Path('app/services')
    services = []
    for py_file in sorted(services_dir.glob('*.py')):
        if py_file.name.startswith('__'):
            continue
        services.append(py_file.stem)
    
    f.write(f"Total Services: {len(services)}\n\n")
    
    # Check if service has corresponding API
    api_dir = Path('app/api/v1')
    api_files = [f.stem for f in api_dir.glob('*.py') if not f.name.startswith('__')]
    
    f.write("Service to API Mapping:\n")
    f.write("-" * 60 + "\n")
    
    for service in sorted(services):
        # Check if there's a corresponding API file
        api_match = [a for a in api_files if service in a or a in service]
        if api_match:
            f.write(f"  [OK] {service}.py -> {api_match[0]}.py\n")
        else:
            f.write(f"  [WARN] {service}.py (no corresponding API)\n")
    
    # ==========================================
    # 3. Model Layer Check
    # ==========================================
    f.write("\n" + "=" * 80 + "\n")
    f.write("[3] MODEL LAYER COMPLETION CHECK\n")
    f.write("=" * 80 + "\n\n")
    
    models_dir = Path('app/models')
    models = []
    for py_file in sorted(models_dir.glob('*.py')):
        if py_file.name.startswith('__'):
            continue
        content = py_file.read_text(encoding='utf-8')
        classes = re.findall(r'class\s+(\w+)\(Base\)', content)
        for cls in classes:
            models.append(f"{py_file.stem}.{cls}")
    
    f.write(f"Total ORM Models: {len(models)}\n\n")
    
    # ==========================================
    # 4. Database Tables Check
    # ==========================================
    f.write("=" * 80 + "\n")
    f.write("[4] DATABASE TABLES CHECK\n")
    f.write("=" * 80 + "\n\n")
    
    f.write("Expected tables based on models:\n")
    f.write("-" * 60 + "\n")
    
    expected_tables = [
        'users', 'roles', 'agents', 'model_config_templates',
        'conversations', 'messages', 'skills', 'skill_bindings',
        'mcps', 'workspaces', 'workspace_members',
        'model_template_versions', 'model_template_bindings',
        'token_usages', 'token_budgets', 'token_alerts',
        'agent_memories', 'memory_analytics',
        'audit_logs', 'audit_archives', 'audit_rules',
        'backup_records', 'backup_policies', 'restore_operations',
        'health_check_runs', 'health_snapshots',
        'collaboration_tasks', 'collaboration_agents',
        'notification_configs',
    ]
    
    for table in expected_tables:
        f.write(f"  - {table}\n")
    
    f.write(f"\nTotal expected tables: {len(expected_tables)}\n")
    
    # ==========================================
    # 5. API Response Format Check
    # ==========================================
    f.write("\n" + "=" * 80 + "\n")
    f.write("[5] API RESPONSE FORMAT CONSISTENCY\n")
    f.write("=" * 80 + "\n\n")
    
    # Check response formats
    response_formats = defaultdict(int)
    for route in app.routes:
        if hasattr(route, 'endpoint') and route.endpoint:
            annotations = getattr(route.endpoint, '__annotations__', {})
            if 'return' in annotations:
                return_type = str(annotations['return'])
                response_formats[return_type] += 1
    
    f.write("Response Type Distribution:\n")
    for resp_type, count in sorted(response_formats.items(), key=lambda x: -x[1])[:10]:
        f.write(f"  {resp_type}: {count} endpoints\n")
    
    # ==========================================
    # 6. TODO/FIXME Check
    # ==========================================
    f.write("\n" + "=" * 80 + "\n")
    f.write("[6] TODO/FIXME ITEMS\n")
    f.write("=" * 80 + "\n\n")
    
    todos = []
    for py_file in Path('app').rglob('*.py'):
        if py_file.name.startswith('__'):
            continue
        content = py_file.read_text(encoding='utf-8')
        for match in re.finditer(r'#\s*(TODO|FIXME|HACK|XXX):\s*(.*)', content, re.IGNORECASE):
            todos.append((py_file.stem, match.group(1), match.group(2).strip()))
    
    if todos:
        f.write(f"Found {len(todos)} TODO/FIXME items:\n\n")
        for todo in todos[:15]:
            f.write(f"  [{todo[1]}] {todo[0]}.py: {todo[2]}\n")
        if len(todos) > 15:
            f.write(f"  ... and {len(todos) - 15} more\n")
    else:
        f.write("No TODO/FIXME items found\n")
    
    # ==========================================
    # 7. Final Summary
    # ==========================================
    f.write("\n" + "=" * 80 + "\n")
    f.write("FINAL SUMMARY\n")
    f.write("=" * 80 + "\n\n")
    
    f.write(f"Features Completed: {completed_count}/{total_features} ({completed_count/total_features*100:.1f}%)\n")
    f.write(f"Services Created: {len(services)}\n")
    f.write(f"ORM Models: {len(models)}\n")
    f.write(f"Expected Tables: {len(expected_tables)}\n")
    f.write(f"TODO Items: {len(todos)}\n\n")
    
    if incomplete_features:
        f.write("Features Needing Implementation:\n")
        f.write("-" * 60 + "\n")
        for feature, missing in incomplete_features:
            f.write(f"  - {feature}\n")
    
    f.write("\n" + "=" * 80 + "\n")
    f.write("CHECK COMPLETE\n")
    f.write("=" * 80 + "\n")

print(f"Feature check complete. Results saved to {output}")
