import sys
import asyncio
import logging
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from composer import Agent, Thread
from composer.config import MCPClient
from penta.agents.common import (
    llm, 
    get_mcp_skills, 
    get_or_create_from_task, 
    update_task, 
    update_chat_session,
)
from penta.schemas import (
    Task, 
    Part,
    EventQueue,
    AgentSkill,
    AgentCard,
    CheckBreakReason,
)
from penta.enums import Status
from penta.mcps import taskmanager_server, webagent_server
from penta.prompts import form_discovery_agent_prompt, input_required
from typing import Optional, cast

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_handler)


client = MCPClient(
    servers=[taskmanager_server, webagent_server],
)

tools = asyncio.run(client.get_tools()) or []

agent = Agent(
    model=llm,
    tools=tools,
    response_schema=CheckBreakReason,
)

form_discovery_agent_skill = AgentSkill(
    name="forms and extended directory discovery",
    skill=(
        "Agent having access of browser finding forms and newer directory discovery with status updation"
        "and taskmanager mcp to update and add found forms in `forms` table"
        "with the status update in `directories` table."
        "and new dir with the status in `directories` table."
    ),
)

form_discovery_agent_card = AgentCard(
    name="form_discovery_agent",
    description=(
        "Sub-agent that discovers forms into existing taskmanager tables. "
        "Query MUST include task_id, directories table_id, forms table_id, "
        "a batch of pending directory URLs (max 5), and rules."
    ),
    skills=[form_discovery_agent_skill]
)

async def form_discovery_agent(task: Task):
    skill = ""
    skill_servers = [taskmanager_server, webagent_server]
    for server in skill_servers:
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
    
    if thread is None:
        thread = Thread()
        thread.append(
            SystemMessage(
                form_discovery_agent_prompt.format(
                    skill=skill,
                ) + input_required
            )
        )
    thread.append(HumanMessage(content=task.query))
    response = await agent.ainvoke(thread)

    if not isinstance(response, dict):
        raise TypeError(f"Expected structured output, got {type(response).__name__}")

    parsed = cast(Optional[CheckBreakReason], response["parsed"])
    if parsed is None:
        await update_task(task, event_queue, Part(
            status=Status.FAILED,
            text=f"Parse error: {response['parsing_error']}",
        ))
    elif parsed.status == "input_required":
        await update_task(task, event_queue, Part(
            status=Status.INPUT_REQUIRED,
            text=parsed.model_dump_json(indent=4),
        ))
    else:
        response = list(thread)[-1]
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

    event_queue_dump = event_queue.model_dump_json(indent=4)
    logger.info(event_queue_dump)

    return(event_queue_dump)