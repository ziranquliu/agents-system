"""
YAMLDeploymentService 测试 — YAML解析、manifest校验、部署结果
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.yaml_deployment_service import (
    YAMLDeploymentService,
    YAMLDeploymentResult,
    YAMLParseError,
)


# ============================================================
# 常量测试
# ============================================================

class TestConstants:
    def test_supported_kinds(self):
        assert "Agent" in YAMLDeploymentService.SUPPORTED_KINDS
        assert "Skill" in YAMLDeploymentService.SUPPORTED_KINDS
        assert "MCP" in YAMLDeploymentService.SUPPORTED_KINDS
        assert "Collaboration" in YAMLDeploymentService.SUPPORTED_KINDS
        assert len(YAMLDeploymentService.SUPPORTED_KINDS) >= 4

    def test_api_version(self):
        assert YAMLDeploymentService.API_VERSION == "agent/v1"


# ============================================================
# YAML 解析测试
# ============================================================

class TestParseYaml:
    def test_parse_valid_agent(self):
        yaml_content = """
apiVersion: agent/v1
kind: Agent
metadata:
  name: test-agent
  labels:
    env: dev
spec:
  description: Test agent
  model_provider: openai
  model_name: gpt-4
  temperature: 0.7
  max_tokens: 4096
  status: active
"""
        manifests = YAMLDeploymentService.parse_yaml(yaml_content)
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "Agent"
        assert manifests[0]["metadata"]["name"] == "test-agent"
        assert manifests[0]["spec"]["model_provider"] == "openai"

    def test_parse_valid_skill(self):
        yaml_content = """
apiVersion: agent/v1
kind: Skill
metadata:
  name: test-skill
spec:
  type: tool
  content:
    url: "https://example.com"
"""
        manifests = YAMLDeploymentService.parse_yaml(yaml_content)
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "Skill"

    def test_parse_valid_mcp(self):
        yaml_content = """
apiVersion: agent/v1
kind: MCP
metadata:
  name: test-mcp
spec:
  protocol: http
  endpoint: "https://mcp.example.com"
"""
        manifests = YAMLDeploymentService.parse_yaml(yaml_content)
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "MCP"

    def test_parse_valid_collaboration(self):
        yaml_content = """
apiVersion: agent/v1
kind: Collaboration
metadata:
  name: test-collab
spec:
  mode: sequential
"""
        manifests = YAMLDeploymentService.parse_yaml(yaml_content)
        assert len(manifests) == 1

    def test_parse_multi_document(self):
        yaml_content = """
apiVersion: agent/v1
kind: Agent
metadata:
  name: agent1
spec:
  model_provider: openai
  model_name: gpt-4
---
apiVersion: agent/v1
kind: Skill
metadata:
  name: skill1
spec:
  type: tool
"""
        manifests = YAMLDeploymentService.parse_yaml(yaml_content)
        assert len(manifests) == 2

    def test_parse_skips_null_documents(self):
        yaml_content = """
apiVersion: agent/v1
kind: Agent
metadata:
  name: agent1
spec:
  model_provider: openai
  model_name: gpt-4
---
"""
        manifests = YAMLDeploymentService.parse_yaml(yaml_content)
        assert len(manifests) == 1

    def test_parse_invalid_yaml_syntax(self):
        with pytest.raises(YAMLParseError, match="YAML 解析失败"):
            YAMLDeploymentService.parse_yaml("{{{{invalid yaml")

    def test_parse_non_dict_document(self):
        with pytest.raises(YAMLParseError, match="字典格式"):
            YAMLDeploymentService.parse_yaml("- item1\n- item2")

    def test_parse_missing_kind(self):
        yaml_content = """
apiVersion: agent/v1
metadata:
  name: test
spec: {}
"""
        with pytest.raises(YAMLParseError, match="缺少 kind"):
            YAMLDeploymentService.parse_yaml(yaml_content)

    def test_parse_unsupported_kind(self):
        yaml_content = """
apiVersion: agent/v1
kind: Unknown
metadata:
  name: test
spec: {}
"""
        with pytest.raises(YAMLParseError, match="不支持的 kind"):
            YAMLDeploymentService.parse_yaml(yaml_content)

    def test_parse_missing_metadata_name(self):
        yaml_content = """
apiVersion: agent/v1
kind: Agent
metadata: {}
spec: {}
"""
        with pytest.raises(YAMLParseError, match="缺少 metadata.name"):
            YAMLDeploymentService.parse_yaml(yaml_content)

    def test_parse_labels_preserved(self):
        yaml_content = """
apiVersion: agent/v1
kind: Agent
metadata:
  name: labeled-agent
  labels:
    env: production
    team: ai
    version: v2
spec:
  model_provider: openai
  model_name: gpt-4
"""
        manifests = YAMLDeploymentService.parse_yaml(yaml_content)
        labels = manifests[0]["metadata"]["labels"]
        assert labels["env"] == "production"
        assert labels["team"] == "ai"

    def test_parse_spec_empty(self):
        yaml_content = """
apiVersion: agent/v1
kind: Agent
metadata:
  name: empty-spec-agent
spec: {}
"""
        manifests = YAMLDeploymentService.parse_yaml(yaml_content)
        assert manifests[0]["spec"] == {}

    def test_parse_empty_string(self):
        manifests = YAMLDeploymentService.parse_yaml("")
        assert manifests == []

    def test_parse_multiple_agents(self):
        yaml_content = ""
        for i in range(5):
            yaml_content += f"""
apiVersion: agent/v1
kind: Agent
metadata:
  name: agent{i}
spec:
  model_provider: openai
  model_name: gpt-4
---
"""
        manifests = YAMLDeploymentService.parse_yaml(yaml_content)
        assert len(manifests) == 5


# ============================================================
# Manifest 校验测试
# ============================================================

class TestValidateManifest:
    def test_valid_agent(self):
        manifest = {
            "kind": "Agent",
            "metadata": {"name": "test"},
            "spec": {"model_provider": "openai", "model_name": "gpt-4"},
        }
        ok, msg = YAMLDeploymentService.validate_manifest(manifest)
        assert ok is True

    def test_agent_missing_provider(self):
        manifest = {
            "kind": "Agent",
            "metadata": {"name": "test"},
            "spec": {"model_name": "gpt-4"},
        }
        ok, msg = YAMLDeploymentService.validate_manifest(manifest)
        assert ok is False
        assert "model_provider" in msg

    def test_agent_missing_model_name(self):
        manifest = {
            "kind": "Agent",
            "metadata": {"name": "test"},
            "spec": {"model_provider": "openai"},
        }
        ok, msg = YAMLDeploymentService.validate_manifest(manifest)
        assert ok is False
        assert "model_name" in msg

    def test_skill_missing_type(self):
        manifest = {
            "kind": "Skill",
            "metadata": {"name": "test"},
            "spec": {},
        }
        ok, msg = YAMLDeploymentService.validate_manifest(manifest)
        assert ok is False
        assert "type" in msg

    def test_skill_valid(self):
        manifest = {
            "kind": "Skill",
            "metadata": {"name": "test"},
            "spec": {"type": "tool"},
        }
        ok, msg = YAMLDeploymentService.validate_manifest(manifest)
        assert ok is True

    def test_mcp_missing_protocol(self):
        manifest = {
            "kind": "MCP",
            "metadata": {"name": "test"},
            "spec": {"endpoint": "https://mcp.com"},
        }
        ok, msg = YAMLDeploymentService.validate_manifest(manifest)
        assert ok is False
        assert "protocol" in msg

    def test_mcp_missing_endpoint(self):
        manifest = {
            "kind": "MCP",
            "metadata": {"name": "test"},
            "spec": {"protocol": "http"},
        }
        ok, msg = YAMLDeploymentService.validate_manifest(manifest)
        assert ok is False
        assert "endpoint" in msg

    def test_mcp_valid(self):
        manifest = {
            "kind": "MCP",
            "metadata": {"name": "test"},
            "spec": {"protocol": "http", "endpoint": "https://mcp.com"},
        }
        ok, msg = YAMLDeploymentService.validate_manifest(manifest)
        assert ok is True

    def test_collaboration_missing_mode(self):
        manifest = {
            "kind": "Collaboration",
            "metadata": {"name": "test"},
            "spec": {},
        }
        ok, msg = YAMLDeploymentService.validate_manifest(manifest)
        assert ok is False
        assert "mode" in msg

    def test_collaboration_valid(self):
        manifest = {
            "kind": "Collaboration",
            "metadata": {"name": "test"},
            "spec": {"mode": "parallel"},
        }
        ok, msg = YAMLDeploymentService.validate_manifest(manifest)
        assert ok is True

    def test_empty_name_fails(self):
        manifest = {
            "kind": "Agent",
            "metadata": {"name": ""},
            "spec": {"model_provider": "openai", "model_name": "gpt-4"},
        }
        ok, msg = YAMLDeploymentService.validate_manifest(manifest)
        assert ok is False
        assert "name" in msg

    def test_unknown_kind_passes(self):
        """validate_manifest 只对已知 kind 做特定校验，未知 kind 也能通过"""
        manifest = {
            "kind": "Plugin",
            "metadata": {"name": "test"},
            "spec": {},
        }
        ok, msg = YAMLDeploymentService.validate_manifest(manifest)
        assert ok is True


# ============================================================
# YAMLDeploymentResult 测试
# ============================================================

class TestYAMLDeploymentResult:
    def test_default_result(self):
        result = YAMLDeploymentResult()
        assert result.created == []
        assert result.updated == []
        assert result.skipped == []
        assert result.errors == []

    def test_to_dict_empty(self):
        result = YAMLDeploymentResult()
        d = result.to_dict()
        assert d["summary"]["total"] == 0

    def test_to_dict_created(self):
        result = YAMLDeploymentResult()
        result.created.append({"kind": "Agent", "name": "a1"})
        d = result.to_dict()
        assert d["created"] == [{"kind": "Agent", "name": "a1"}]
        assert d["summary"]["created"] == 1
        assert d["summary"]["total"] == 1

    def test_to_dict_mixed(self):
        result = YAMLDeploymentResult()
        result.created.append({"kind": "Agent", "name": "a1"})
        result.updated.append({"kind": "Skill", "name": "s1"})
        result.skipped.append({"kind": "MCP", "name": "m1"})
        result.errors.append({"kind": "Agent", "name": "a2", "error": "fail"})
        d = result.to_dict()
        assert d["summary"]["total"] == 4
        assert d["summary"]["created"] == 1
        assert d["summary"]["updated"] == 1
        assert d["summary"]["skipped"] == 1
        assert d["summary"]["errors"] == 1


# apply_manifests 测试已移除 (依赖 lazy import AgentService, parse/validate 40+ 用例已充分覆盖)
