from langchain_core.tools import tool
from penta.schemas import Task, InvokeAgentRequest
import asyncio

@tool(
    "invoke_agent",
    description=(
        "Invoke agent to assign task to perform particular task"
        "Work on agent communication channel protocol"
    ),
    args_schema=InvokeAgentRequest
)
async def invoke_agent(
    name: str,
    query: str,
    channel: str | None = None,
    a2a_task_id: str | None = None
):
    from penta.agents.discovery import agents

    try:
        if name in agents:
            return await agents[name](
                Task(
                    query=query,
                    channel=channel,
                    a2a_task_id=a2a_task_id
                )
            )
        else:
            return f"wrong agent name provided {name}"
    except Exception as e:
        return str(e)

@tool("terminal", description="It's a tool to execute terminal commands")
async def local_terminal(command: str):
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        return f"Error: {stderr.decode()}"
    return {
        "output": stdout.decode(),
        "error": stderr.decode(),
        "returncode": process.returncode,
    }
