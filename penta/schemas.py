from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Any
from penta.enums import Status


class Task(BaseModel):
    query: str
    channel: Optional[str] = None
    a2a_task_id: Optional[str] = None

class Part(BaseModel):
    status: Status
    text: str

class Event(BaseModel):
    query: str
    a2a_task_id: str
    parts: List[Part]

class EventQueue(BaseModel):
    channel: str
    events: List[Event] = []

class InvokeAgentRequest(BaseModel):
    name: str = "Name of Agent to assign task"
    query: str
    channel: Optional[str] = None
    a2a_task_id: Optional[str] = None

class AgentSkill(BaseModel):
    name: str
    skill: str
    tags: Optional[List[Any]] = None
    examples: Optional[List[Any]] = None

class AgentCard(BaseModel):
    name: str
    description: str
    skills: List[AgentSkill]

class CheckBreakReason(BaseModel):
    status: Literal["input_required", "completed"] = Field(
        "completed", 
        description="status of the final response"
    )
    query: Optional[str] = Field(
        None, 
        description="what input was required, nothing in case of status: `completed` respectively to the user task"
    )
    state: Optional[str] = Field(
        None, 
        description="at what stage you were? and what you did/didn't till now? descriptive as possible"
    )