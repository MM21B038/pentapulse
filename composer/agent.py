import asyncio
import logging
import sys
import threading
import json
from langchain_core.messages import ToolMessage, HumanMessage
from pydantic import BaseModel
from typing import List, Iterator, Any, Optional, Type, cast
from composer.thread import Thread
from composer.internal import InternalTools
from composer.llm import LLM

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_handler)

def run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: List[Any] = []
    error = []

    def runner():
        try:
            result.append(asyncio.run(coro))
        except BaseException as e:
            error.append(e)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()

    if error:
        raise error[0]

    return result[0]

class Agent:
    def __init__(self, model: LLM, tools: Optional[List] = None, response_schema: Optional[Type[BaseModel]] = None):
        self.model = model.connect()
        self.structured_model = self.model.with_structured_output(
            response_schema,
            include_raw=True,
        ) if response_schema else None
        self.tools = tools
        self.tool_map = {}
        if self.tools:
            self.tools.extend(InternalTools.tools())
            self.model = self.model.bind_tools(self.tools)
            self.tool_map = {tool.name: tool for tool in self.tools}

    async def invoke_tool(self, name: str, args: dict):
        logger.info(f"Invoking tool: {name}")
        try:
            result = await self.tool_map[name].ainvoke(args)
            logger.info(f"Invoked tool: {name} completed successfully")
        except Exception as e:
            result = f"Error: {e}"
            logger.info(f"Invoked tool: {name} completed with error: {e}")
        if isinstance(result, dict):
            result = json.dumps(result, indent=2, ensure_ascii=False)
        if not isinstance(result, str):
            result = str(result)
        return result

    async def ainvoke(self, thread: Thread, self_append: bool = True):
        if thread.tail is not None:
            thread = thread.tail
        thread.agent = cast(Any, self)
        while True:
            response = await self.model.ainvoke(list(thread))
            
            if not self_append:
                thread.agent = None
                return response
                
            thread.append(response)
            if response.tool_calls:
                logger.info(f"Total tool calls: {len(response.tool_calls)}")
                logger.info(f"Tool calls: {[tool['name'] for tool in response.tool_calls]}")

                async def run_call(tool):
                    result = await self.invoke_tool(tool["name"], tool["args"])
                    return ToolMessage(
                        name=tool["name"],
                        content=result,
                        tool_call_id=tool["id"],
                    )

                for tool_message in await asyncio.gather(
                    *(run_call(tool) for tool in response.tool_calls)
                ):
                    thread.append(tool_message)

            else:
                thread.agent = None
                if self.structured_model is not None:
                    return await self.structured_model.ainvoke(
                        list(thread) + [HumanMessage("Return your final answer in the required structured format.")]
                    )
                return response

    def invoke(self, thread: Thread, self_append: bool = True):
        return run_sync(
            self.ainvoke(
                thread=thread, 
                self_append=self_append
            )
        )
    
    def stream(
        self,
        thread: Thread,
        self_append: bool = True,
    ) -> Iterator[Any]:

        if thread.tail is not None:
            thread = thread.tail

        thread.agent = cast(Any, self)

        try:
            while True:
                response: Any = None
                for chunk in self.model.stream(list(thread)):
                    yield chunk

                    if response is None:
                        response = chunk
                    else:
                        response = response + chunk
                        
                if not self_append:
                    return

                if response is None:
                    return

                thread.append(response)

                if response.tool_calls:
                    for tool in response.tool_calls:
                        args = tool["args"]
                        call_id = tool["id"]
                        name = tool["name"]

                        try:
                            result = self.tool_map[name].invoke(args)
                        except Exception as e:
                            result = f"Error: {e}"

                        tool_message = ToolMessage(
                            name=name,
                            content=result,
                            tool_call_id=call_id,
                        )

                        thread.append(tool_message)


                else:
                    return

        finally:
            thread.agent = None


    def __ror__(self, thread: Thread):
        return self.invoke(thread)