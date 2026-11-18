import os
import uuid
from composer.config import Server, MCPClient
from composer import LLM, Thread
from composer.enum import LLMProvider
from penta.schemas import (
    Task,
    Part,
    Event,
    EventQueue,
    AgentCard
)
from penta.enums import Status
from mongo.client import get_chat_sessions_collection, get_event_queue_collection
from typing import List
from dotenv import load_dotenv

load_dotenv()

async def get_mcp_skills(skill: str | None, server: Server, client: MCPClient):
    if skill is None or skill.strip() == "":
        skill = (
            "#########"
            "SKILLS"
            "#########"
        )
    prompts = await client.list_prompts(server.name)
    if not prompts:
        return
    skills = await client.get_prompt(server.name, prompts[0].name)
    if isinstance(skills, list) and len(skills) > 0:
        skill = f"{skill}\n{skills[0].content}\n---\n"
    return

async def get_structured_agent_cards_info(cards: List[AgentCard]):
    structured_cards_info = (
        ""
        "###########"
        "Agent Cards"
        "###########"
        ""
    )
    for card in cards:
        structured_cards_info += (
            "```json"
            f"{card.model_dump_json(indent=4)}"
            "```"
            ""
        )
    return structured_cards_info

async def get_or_create_from_task(task: Task):
    if task.channel:
        event_queue_collection = get_event_queue_collection()
        existing_queue = event_queue_collection.find_one({"channel": str(task.channel)})
        if not existing_queue:
            return f"channel id: {task.channel} not exist", None
        event_queue_list = existing_queue["events"] if existing_queue else {}
        event_queue = EventQueue(
            channel=task.channel, 
            events=[
                Event(
                    query=e["query"],
                    a2a_task_id=e["a2a_task_id"],
                    parts=[
                        Part(status=Status(p["status"]), text=p["text"]) 
                        for p in e["parts"]
                        ]
                    ) 
                for e in event_queue_list
                ]
            )
        chat_sessions_collection = get_chat_sessions_collection()
        chat_session = chat_sessions_collection.find_one({"channel": str(task.channel)})
        chats = chat_session["chats"] if chat_session else []
        thread = Thread.from_model_dump(chats)
            
    else:
        channel=str(uuid.uuid4())
        task.channel=channel
        get_event_queue_collection().insert_one({"channel": str(channel), "events": []})
        get_chat_sessions_collection().insert_one({"channel": str(channel), "chats": []})
        event_queue = EventQueue(channel=channel, events=[])
        thread = None

    if task.a2a_task_id and task.a2a_task_id not in [e.a2a_task_id for e in event_queue.events]:
        return f"a2a task id: {task.a2a_task_id} not exist within the {task.channel} id you have provided", None
    
    return event_queue, thread

async def update_task(task: Task, event_queue: EventQueue, part: Part):
    if task.a2a_task_id:
        if task.a2a_task_id not in [e.a2a_task_id for e in event_queue.events]:
            return False
        for e in event_queue.events:
            if e.a2a_task_id == task.a2a_task_id:
                e.parts.append(part)
                break
    else:
        task.a2a_task_id = str(uuid.uuid4())
        event_queue.events.append(
            Event(
                query=task.query,
                a2a_task_id=task.a2a_task_id,
                parts=[
                    part
                ],
            )
        )
    get_event_queue_collection().update_one(
        {"channel": task.channel},
        {"$set": {"events": [event.model_dump() for event in event_queue.events]}},
    )

    return True
    
async def update_chat_session(task: Task, thread: Thread):
    get_chat_sessions_collection().update_one(
        {"channel": task.channel},
        {"$set": {"chats": thread.model_dump()}},
    )

llm = LLM(
    provider=LLMProvider.OPENAI,
    model=os.getenv("LLM", "gpt-5.4-mini"),
    # base_url=os.getenv("BASE_URL", "http://localhost:5050/gateway/mlflow/v1"),
    api_key=os.getenv("API_KEY", "************"),
)