import sys
import uuid
import asyncio
import typer
import logging
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from composer import Agent, Thread
from composer.config import MCPClient
from penta.prompts import (
    orchestrator_prompt,
    a2a_channel_protocol
)
from penta.agents.common import (
    llm, 
    get_mcp_skills, 
    get_structured_agent_cards_info,
    get_or_create_from_task, 
    update_task, 
    update_chat_session,
)
from penta.agents.tools import invoke_agent
from penta.schemas import Task, Part, EventQueue
from penta.enums import Status
from penta.mcps import taskmanager_server
from penta.agents.discovery import (
    directory_discovery_agent_card,
    form_discovery_agent_card,
    priority_assigning_agent_card,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_handler)


client = MCPClient(
    servers=[taskmanager_server],
)

tools = asyncio.run(client.get_tools()) or []

agent = Agent(
    model=llm,
    tools=tools + [invoke_agent],
)

async def run_orchestrator(task: Task):

    skill = ""
    for server in [taskmanager_server]:
        try:
            await get_mcp_skills(skill, server, client)
            logger.info(f"Loaded skills for {server.name} MCP server successfully")
        except Exception as e:
            logger.error(f"Failed to load skills for {server.name} MCP server: {e}")
            pass

    query = task.query

    event_queue, thread = await get_or_create_from_task(task)
    if not isinstance(event_queue, EventQueue):
        return event_queue

    await update_task(
        task,
        event_queue,
        Part(
            status=Status.RECEIVED,
            text=query
        )
    )

    sys = orchestrator_prompt.format(
        skill=skill,
    )
    sys += a2a_channel_protocol
    sys += await get_structured_agent_cards_info(
        [
            directory_discovery_agent_card, 
            form_discovery_agent_card,
            priority_assigning_agent_card
        ]
    )
    
    if thread is None:
        thread = Thread()
        thread.append(
            SystemMessage(
                sys
            )
        )
    thread.append(HumanMessage(content=task.query))

    await update_task(
        task,
        event_queue,
        Part(
            status=Status.WORKING,
            text="working on your query"
        )
    )
    response = await agent.ainvoke(thread)

    await update_task(
        task,
        event_queue,
        Part(
            status=Status.COMPLETED,
            text=str(response.content) if isinstance(response, AIMessage) else "Error AIMessage not recieved"
        )
    )

    await update_chat_session(
        task,
        thread
    )

    logger.info(event_queue.model_dump_json(indent=4))


app = typer.Typer()

@app.command(name="orchestrator")
def run(
    query: str = typer.Argument(..., help="The query to run the orchestrator"),
    channel: str = typer.Option(None, help="The channel UUID to send events to"),
    a2a_task_id: str = typer.Option(None, help="The A2A task ID to associate with the query")
):
    task = Task(query=query, channel=str(uuid.UUID(channel)) if channel else None, a2a_task_id=a2a_task_id or None)
    asyncio.run(run_orchestrator(task))

if __name__ == "__main__":
    app()