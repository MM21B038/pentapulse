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
    update_chat_session
)
from penta.agents.tools import local_terminal
from penta.skills.recon import recon_skill
from penta.schemas import (
    Task, 
    Part,
    EventQueue,
    AgentSkill,
    AgentCard,
    CheckBreakReason,
)
from penta.enums import Status
from penta.mcps import taskmanager_server, webagent_server, recon_server
from penta.prompts import directory_discovery_agent_prompt, input_required
from typing import Optional, cast

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_handler)


client = MCPClient(
    servers=[taskmanager_server, recon_server, webagent_server],
)

tools = asyncio.run(client.get_tools()) or []

agent = Agent(
    model=llm,
    tools=tools + [local_terminal],
    response_schema=CheckBreakReason,
)

directory_discovery_agent_skill = AgentSkill(
    name="directory discovery",
    skill=(
        "Agent having access to the traditional recon tools that have capabilities of crawlling and force dir finding"
        "It was also having access of browser as well for crawling and checking status as well"
        "and taskmanager mcp to update and add found dir with the status in `directories` table."
    ),
)

directory_discovery_agent_card = AgentCard(
    name="directory_discovery_agent",
    description=(
        "Agent that discovers directories and register into an existing taskmanager table. "
        "Query MUST include target URL, task_id, directories table_id, and rules. "
    ),
    skills=[directory_discovery_agent_skill]
)

async def directory_discovery_agent(task: Task):
    skill = ""
    skill_servers = [taskmanager_server, webagent_server]
    for server in skill_servers:
        try:
            await get_mcp_skills(skill, server, client)
            logger.info(f"Loaded skills for {server.name} MCP server successfully")
        except Exception as e:
            logger.error(f"Failed to load skills for {server.name} MCP server: {e}")
            pass

    skill += f"\n##########\nSKILL TO PERFORM RECON\n##########\n\n{recon_skill}\n---\n"
    logger.info("Loaded recon skill successfully")

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
                directory_discovery_agent_prompt.format(
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