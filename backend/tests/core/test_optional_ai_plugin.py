import tomllib
from pathlib import Path

import pytest

from app.core import plugins
from app.core.plugins import filter_ai_seed_data, get_ai_routers


def test_builtin_ai_plugin_ignores_legacy_switch(monkeypatch):
    """AI 路由不再受旧的 AI_ENABLE 开关影响。"""
    monkeypatch.setenv("AI_ENABLE", "false")

    routers = get_ai_routers()

    assert any("/ai/knowledge/list" in route.path for router in routers for route in router.routes)


def test_core_application_registers_builtin_ai_routes():
    """核心应用始终注册 AI 路由。"""
    from main import create_app

    app = create_app()

    assert any(route.path == "/ai/knowledge/list" for route in app.routes)


def test_builtin_ai_seed_data_is_not_filtered():
    """内置 AI 的菜单和权限种子数据保持完整。"""
    records = [{"route_name": "AI", "component_path": "module_ai/knowledge"}]

    assert filter_ai_seed_data("platform_menu", records) is records
    assert filter_ai_seed_data("sys_role_menus", records) is records


def test_ai_dependencies_are_default_backend_dependencies():
    """AI packages must be installed with the default backend profile."""
    pyproject_path = Path(__file__).parents[2] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    required_modules = {
        "chromadb",
        "fastembed",
        "jieba",
        "openai",
        "pypdf",
        "python-docx",
        "whoosh",
    }
    base_dependencies = {
        dependency.split("[", maxsplit=1)[0].split("=", maxsplit=1)[0].split(">", maxsplit=1)[0].split("<", maxsplit=1)[0]
        for dependency in pyproject["project"]["dependencies"]
    }

    assert required_modules <= base_dependencies
    assert "ai" not in pyproject["project"].get("optional-dependencies", {})
    manifest = tomllib.loads((Path(__file__).parents[2] / "app/plugin/module_ai/plugin.toml").read_text(encoding="utf-8"))
    assert "optional" not in manifest
    assert "enabled_env" not in manifest


def test_customer_kb_manifest_exposes_knowledge_routes_only():
    manifest = tomllib.loads((Path(__file__).parents[2] / "app/plugin/module_ai/plugin.toml").read_text(encoding="utf-8"))

    assert manifest["websocket_routers"] == []
    assert manifest["routers"] == [
        "chat.controller:ChatRouter",
        "knowledge.controller:KnowledgeRouter",
        "knowledge.app_data.controller:AppDataRouter",
    ]
    assert not any(permission.startswith(("module_ai:chat:", "module_ai:session:", "module_ai:memory:")) for permission in manifest["permissions"])


def test_builtin_ai_plugin_fails_fast_when_dependency_is_missing(monkeypatch):
    """内置 AI 缺依赖时应明确失败，不再静默返回 404。"""
    original_find_spec = plugins.importlib.util.find_spec

    def find_spec(module_name: str):
        if module_name == "chromadb":
            return None
        return original_find_spec(module_name)

    monkeypatch.setattr(plugins.importlib.util, "find_spec", find_spec)
    with pytest.raises(RuntimeError, match="内置依赖"):
        plugins.is_ai_plugin_enabled()
