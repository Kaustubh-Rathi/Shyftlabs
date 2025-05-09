#orchestrator.py
import os
import datetime
import json
import sys
import asyncio
import logging
import traceback
from langgraph.graph import StateGraph, END
from .utils.views import print_agent_output
from ..memory.research import ResearchState
from .utils.utils import sanitize_filename
from .utils.vector_index import create_vector_index, add_to_global_vector_store

from . import WriterAgent, EditorAgent, PublisherAgent, ResearchAgent, HumanAgent

logger = logging.getLogger(__name__)

class WebSocketOutput:
    def __init__(self, websocket, stream_output, type="logs", subtype="terminal"):
        self.websocket = websocket
        self.stream_output = stream_output
        self.type = type
        self.subtype = subtype
        self.queue = asyncio.Queue()
        self.task = None
        self.original_stdout = sys.__stdout__  # Store reference to system stdout
        # Only start the sender task if websocket is provided
        if websocket:
            self.task = asyncio.create_task(self._sender())
        else:
            logger.warning("WebSocket is None, messages will be printed to console")

    async def _sender(self):
        while True:
            message = await self.queue.get()
            try:
                if self.websocket:  # Double-check websocket exists
                    await self.stream_output(self.type, self.subtype, message.rstrip(), self.websocket)
                    logger.debug(f"Sent terminal output: {message.rstrip()}")
                else:
                    self.original_stdout.write(f"Cannot send (websocket is None): {message.rstrip()}\n")
                    self.original_stdout.flush()
            except Exception as e:
                logger.error(f"Error sending terminal output: {e}")
                self.original_stdout.write(f"Failed to send: {message.rstrip()}\n")
                self.original_stdout.flush()

    def write(self, s):
        if s:  # Capture all non-empty outputs, including partial writes
            if self.task:  # If sender task exists, queue the message
                self.queue.put_nowait(s)
            else:  # Otherwise use the original stdout to avoid recursion
                self.original_stdout.write(s)
                self.original_stdout.flush()

    def flush(self):
        if hasattr(self.original_stdout, 'flush'):
            self.original_stdout.flush()

class ChiefEditorAgent:
    def __init__(self, task: dict, task_id: str, websocket=None, stream_output=None, tone=None, headers=None):
        self.task = task
        self.task_id = task_id
        self.websocket = websocket
        self.stream_output = stream_output
        self.headers = headers or {}
        self.tone = tone
        self.output_dir = self._create_output_directory()

    def _create_output_directory(self):
        output_dir = f"./outputs/{self.task_id}"
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def _initialize_agents(self):
        return {
            "writer": WriterAgent(self.websocket, self.stream_output, self.headers),
            "editor": EditorAgent(self.websocket, self.stream_output, self.tone, self.headers),
            "research": ResearchAgent(self.websocket, self.stream_output, self.tone, self.headers),
            "publisher": PublisherAgent(self.output_dir, self.websocket, self.stream_output, self.headers),
            "human": HumanAgent(self.websocket, self.stream_output, self.headers)
        }

    def _create_workflow(self, agents):
        workflow = StateGraph(ResearchState)
        workflow.add_node("browser", agents["research"].run_initial_research)
        workflow.add_node("planner", agents["editor"].plan_research)
        workflow.add_node("researcher", agents["editor"].run_parallel_research)
        workflow.add_node("writer", agents["writer"].run)
        workflow.add_node("publisher", agents["publisher"].run)
        workflow.add_node("human", agents["human"].review_plan)
        self._add_workflow_edges(workflow)
        return workflow

    def _add_workflow_edges(self, workflow):
        workflow.add_edge('browser', 'planner')
        workflow.add_edge('planner', 'human')
        workflow.add_edge('researcher', 'writer')
        workflow.add_edge('writer', 'publisher')
        workflow.set_entry_point("browser")
        workflow.add_edge('publisher', END)
        workflow.add_conditional_edges(
            'human',
            lambda review: "accept" if review['human_feedback'] is None else "revise",
            {"accept": "researcher", "revise": "planner"}
        )

    def init_research_team(self):
        agents = self._initialize_agents()
        return self._create_workflow(agents)

    async def _log_research_start(self):
        message = f"Starting the research process for query '{self.task.get('query')}'..."
        if self.websocket and self.stream_output:
            await self.stream_output("logs", "starting_research", message, self.websocket)
        else:
            print_agent_output(message, "MASTER")

    async def run_research_task(self):
        # Store original stdout and stderr
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
        # Create WebSocketOutput with reference to original stdout/stderr
        self.ws_output = WebSocketOutput(self.websocket, self.stream_output)
        
        # Replace stdout and stderr
        sys.stdout = self.ws_output
        sys.stderr = self.ws_output

        try:
            logger.info(f"Initializing research task for {self.task_id}...")
            self.original_stdout.write(f"Initializing research task for {self.task_id}...\n")
            await self._log_research_start()
            research_team = self.init_research_team()
            chain = research_team.compile()
            config = {
                "configurable": {
                    "thread_id": self.task_id,
                    "thread_ts": datetime.datetime.utcnow()
                }
            }
            logger.info(f"Starting agent workflow for {self.task_id}...")
            self.original_stdout.write(f"Starting agent workflow for {self.task_id}...\n")
            result = await chain.ainvoke({"task": self.task}, config=config)
            logger.info(f"Creating vector index for {self.task_id}...")
            self.original_stdout.write(f"Creating vector index for {self.task_id}...\n")
            create_vector_index(result["report"], self.output_dir)
            with open(os.path.join(self.output_dir, "chunks.json"), 'r') as f:
                chunks = json.load(f)
            logger.info(f"Adding to global vector store for {self.task_id}...")
            self.original_stdout.write(f"Adding to global vector store for {self.task_id}...\n")
            add_to_global_vector_store(self.task_id, chunks)
            logger.info(f"Research task completed for {self.task_id}.")
            self.original_stdout.write(f"Research task completed for {self.task_id}.\n")
            return result
        except Exception as e:
            error_msg = f"Research failed for {self.task_id}: {str(e)}\n{''.join(traceback.format_exc())}"
            # Log to both logger and original stdout
            logger.error(error_msg)
            self.original_stdout.write(f"{error_msg}\n")
            self.original_stdout.flush()
            raise
        finally:
            # Always restore original stdout and stderr
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr
            logger.info(f"Stdout and stderr restored for {self.task_id}.")