#main.py
import sys
import os
import logging
import shutil
import json
import uuid
import traceback
import asyncio
from collections import deque
from typing import Dict, Any, Optional, List, Deque

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Adjust path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gpt_researcher.utils.enum import Tone
from multi_agents.agents.utils.vector_index import load_vector_index, retrieve_chunks
from multi_agents.agents.utils.llms import call_model

# ----- In-memory log capture -----
class InMemoryLogHandler(logging.Handler):
    def __init__(self, capacity=1000):
        super().__init__(level=logging.INFO)
        self.buffer = deque(maxlen=capacity)

    def emit(self, record):
        entry = {"name": record.name, "message": record.getMessage()}
        self.buffer.append(entry)

    def read_all(self):
        return list(self.buffer)

    def clear(self):
        self.buffer.clear()

# ----- WebSocket forwarding handler -----
class WebSocketLogHandler(logging.Handler):
    def __init__(self, manager, task_id):
        super().__init__(level=logging.INFO)
        self.manager = manager
        self.task_id = task_id

    def emit(self, record):
        entry = {"type": "log", "name": record.name, "message": record.getMessage()}
        try:
            asyncio.get_event_loop().create_task(
                self.manager.send_message(json.dumps(entry), self.task_id)
            )
        except Exception:
            pass

# ----- Logging setup -----
root = logging.getLogger()
root.setLevel(logging.INFO)
for h in list(root.handlers):
    root.removeHandler(h)

stream = logging.StreamHandler(sys.stdout)
stream.setFormatter(logging.Formatter("%(levelname)s:%(name)s: %(message)s"))
root.addHandler(stream)

memory_handler = InMemoryLogHandler()
root.addHandler(memory_handler)
logging.getLogger("uvicorn").addHandler(memory_handler)
logger = logging.getLogger(__name__)

# ----- FastAPI setup -----
load_dotenv()
app = FastAPI()
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Data Models -----
class ResearchRequest(BaseModel):
    query: str
    tone: str = "Objective"
    max_sections: Optional[int] = 3
    publish_formats: Optional[Dict[str, bool]] = None
    include_human_feedback: Optional[bool] = False
    follow_guidelines: Optional[bool] = True
    model: Optional[str] = "gpt-4"
    guidelines: Optional[List[str]] = None
    verbose: Optional[bool] = True

# ----- Connection Manager -----
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.message_buffers: Dict[str, Deque[Dict[str, Any]]] = {}

    async def connect(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        self.active_connections[task_id] = websocket
        task_queues[task_id] = asyncio.Queue()

        async def sender():
            try:
                while True:
                    message = await task_queues[task_id].get()
                    if websocket.client_state.name != "CONNECTED":
                        break
                    await websocket.send_text(message)
            finally:
                self.disconnect(task_id)

        asyncio.create_task(sender())

        # Drain in-memory logs
        for entry in memory_handler.read_all():
            await task_queues[task_id].put(json.dumps({"type": "log", **entry}))
        memory_handler.clear()

    def disconnect(self, task_id: str):
        self.active_connections.pop(task_id, None)
        task_queues.pop(task_id, None)

    async def send_message(self, message: str, task_id: str):
        if task_id in self.active_connections and task_id in task_queues:
            try:
                await task_queues[task_id].put(message)
            except Exception:
                self._buffer_message(json.loads(message), task_id)
        else:
            self._buffer_message(json.loads(message), task_id)

    def _buffer_message(self, message: Dict[str, Any], task_id: str):
        if task_id not in self.message_buffers:
            self.message_buffers[task_id] = deque(maxlen=1000)
        self.message_buffers[task_id].append(message)

manager = ConnectionManager()
active_tasks: Dict[str, asyncio.Task] = {}
task_queues: Dict[str, asyncio.Queue] = {}

# ----- Chat Query Handler -----
async def handle_chat_query(task_id: str, query: str):
    output_dir = f"./outputs/{task_id}"
    if not os.path.exists(output_dir):
        return "Report not found."

    index, chunks = load_vector_index(output_dir)
    retrieved_chunks = retrieve_chunks(query, index, chunks)
    prompt = f"Based on the following information from the report, answer the question: {query}\n\n" + "\n\n".join(retrieved_chunks)
    return await call_model([{"role": "user", "content": prompt}], model="gpt-3.5-turbo")

# ----- Endpoints -----
@app.get("/logs")
def get_logs():
    return {"logs": memory_handler.read_all()}

@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await manager.connect(websocket, task_id)
    ws_handler = WebSocketLogHandler(manager, task_id)
    root.addHandler(ws_handler)

    try:
        while True:
            data = await websocket.receive_text()
            data = json.loads(data)
            if data.get("type") == "chat_query":
                answer = await handle_chat_query(task_id, data.get("query", ""))
                await manager.send_message(json.dumps({"type": "chat_response", "answer": answer}), task_id)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(task_id)
        root.removeHandler(ws_handler)

@app.post("/start_research")
async def start_research(request: ResearchRequest):
    task_id = str(uuid.uuid4())
    logger.info(f"Starting research task {task_id} with query: {request.query}")

    async def run_task():
        try:
            logger.info(f"Inside run_task for task {task_id}")
            try:
                tone_enum = Tone[request.tone.capitalize()]
            except KeyError:
                tone_enum = Tone.Objective
                logger.warning(f"Unknown tone, defaulting to Objective")

            task = {
                "query": request.query,
                "max_sections": request.max_sections,
                "publish_formats": request.publish_formats or {"markdown": True},
                "include_human_feedback": request.include_human_feedback,
                "follow_guidelines": request.follow_guidelines,
                "model": request.model,
                "guidelines": request.guidelines,
                "verbose": request.verbose
            }

            from multi_agents.agents import ChiefEditorAgent
            current_ws = manager.active_connections.get(task_id)
            chief = ChiefEditorAgent(
                task, task_id, current_ws,
                lambda t, k, m, w: manager.send_message(
                    json.dumps({"type": t, "key": k, "message": m}), task_id
                ),
                tone_enum
            )
            result = await chief.run_research_task()

            output_dir = f"./outputs/{task_id}"
            files_urls = {}
            base = "http://localhost:8000"
            if "files" in result:
                files_urls = {fmt: f"{base}/outputs/{task_id}/{name}" for fmt, name in result["files"].items()}
            else:
                for f in os.listdir(output_dir):
                    if f.endswith((".md", ".pdf", ".docx")):
                        ext = f.split('.')[-1]
                        files_urls[ext] = f"{base}/outputs/{task_id}/{f}"

            await manager.send_message(json.dumps({"type": "complete", "files": files_urls}), task_id)

        except Exception:
            err = traceback.format_exc()
            logger.error(f"Research failed: {err}")
            await manager.send_message(json.dumps({"type": "error", "message": err}), task_id)
        finally:
            logger.info(f"Task {task_id} done")

    active_tasks[task_id] = asyncio.create_task(run_task())
    return {"task_id": task_id, "status": "started"}

@app.get("/task_status/{task_id}")
def get_task_status(task_id: str):
    status = "running" if task_id in active_tasks and not active_tasks[task_id].done() else "completed"
    return {"status": status}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
