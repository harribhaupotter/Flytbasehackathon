from fastapi import APIRouter, Depends, Request
from app.deps import verify_auth
from app.schemas import ToolsResponse, ToolDefinition

router = APIRouter(tags=["Tools"])


@router.get("/tools", response_model=ToolsResponse)
async def list_tools(request: Request, _auth: bool = Depends(verify_auth)):
    """Returns all tools discovered from active MCP servers."""
    mcp_manager = getattr(request.app.state, "mcp_manager", None)
    if not mcp_manager:
        return ToolsResponse(tools=[])

    tools_raw = mcp_manager.get_tools()
    definitions = [
        ToolDefinition(
            name=t["name"],
            description=t.get("description", ""),
            input_schema=t.get("input_schema", {}),
        )
        for t in tools_raw
    ]
    return ToolsResponse(tools=definitions)
