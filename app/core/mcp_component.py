# app/core/mcp_component.py
from __future__ import annotations

import inspect
import logging
from typing import Callable
from fastmcp import FastMCP
from fastmcp.tools import Tool
from fastmcp.tools.function_tool import ToolMeta
from fastmcp.resources import Resource
from fastmcp.resources.function_resource import ResourceMeta
from fastmcp.prompts import Prompt
from fastmcp.prompts.function_prompt import PromptMeta


logger = logging.getLogger(__name__)


class MCPComponent:
    @classmethod
    def register_mcp(cls, mcp: FastMCP, *args, **kwargs) -> None:
        """BaseMCPProvider 의 하위 클래스에서 FastMCP 인스턴스에 Tool, Resource, Prompt 를 등록하는 메서드입니다."""
        new_cls = cls(*args, **kwargs)
        for name, func in inspect.getmembers(new_cls):
            if isinstance(func, Tool) or (hasattr(func, "__fastmcp__") and isinstance(func.__fastmcp__, ToolMeta)):
                logger.debug(f"Registering MCP Tool: {name}")
                mcp.add_tool(func)
            elif isinstance(func, Resource) or (hasattr(func, "__fastmcp__") and isinstance(func.__fastmcp__, ResourceMeta)):
                logger.debug(f"Registering MCP Resource: {name}")
                mcp.add_resource(func)
            elif isinstance(func, Prompt) or (hasattr(func, "__fastmcp__") and isinstance(func.__fastmcp__, PromptMeta)):
                logger.debug(f"Registering MCP Prompt: {name}")
                mcp.add_prompt(func)
        return new_cls
