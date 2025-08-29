
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import asyncio
import json
import time
import uuid
from typing import List, Dict, Any, Optional, AsyncGenerator

app = FastAPI(title="stefan_api_test_1", version="1.0.0")

# Simple CORS: allow everything for simplicity per requirements
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- In-memory storage (volatile) -----
MESSAGES: List[Dict[str, Any]] = []

# SSE subscribers: each subscriber gets its own queue
SUBSCRIBERS: List[asyncio.Queue] = []
SUBSCRIBERS_LOCK = asyncio.Lock()

MAX_LEN = 1000

class MessageCreate(BaseModel):
    text: str = Field(default="", description="Fri text, upp till 1000 tecken (inkl. emojis och radbrytningar)")

class Message(BaseModel):
    id: str
    text: str
    timestamp: float

def make_message(text: str) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "text": text,
        "timestamp": time.time(),
    }

async def broadcast(event: Dict[str, Any]) -> None:
    # fan out to all queues, dropping to slow consumers if needed
    async with SUBSCRIBERS_LOCK:
        dead = []
        for q in SUBSCRIBERS:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            try:
                SUBSCRIBERS.remove(q)
            except ValueError:
                pass

@app.get("/", include_in_schema=False)
async def root() -> Dict[str, str]:
    return {"status": "ok", "service": "stefan_api_test_1"}

@app.get("/messages", response_model=List[Message])
async def list_messages() -> List[Dict[str, Any]]:
    # Return newest first
    return list(reversed(MESSAGES))

@app.post("/messages", response_model=Message, status_code=201)
async def create_message(payload: MessageCreate) -> Dict[str, Any]:
    if payload.text is None:
        raise HTTPException(status_code=400, detail="text saknas")
    if len(payload.text) > MAX_LEN:
        raise HTTPException(status_code=422, detail=f"text får vara max {MAX_LEN} tecken")
    msg = make_message(payload.text)
    MESSAGES.append(msg)
    # broadcast SSE event
    await broadcast({"type": "message.created", "data": msg})
    return msg

async def sse_event_generator(queue: asyncio.Queue) -> AsyncGenerator[bytes, None]:
    try:
        # heartbeat every 20s
        heartbeat = 20
        last = time.time()
        while True:
            try:
                timeout = max(0.0, heartbeat - (time.time() - last))
                event = await asyncio.wait_for(queue.get(), timeout=timeout)
                last = time.time()
                data = json.dumps(event, ensure_ascii=False)
                yield f"event: {event.get('type','message')}\n".encode("utf-8")
                yield f"data: {data}\n\n".encode("utf-8")
            except asyncio.TimeoutError:
                # send heartbeat comment to keep connection open
                last = time.time()
                yield b": ping\n\n"
    except asyncio.CancelledError:
        raise
    finally:
        # cleanup is handled in endpoint
        pass

@app.get("/stream")
async def stream(request: Request):
    """
    Server-Sent Events stream.
    Frontend can connect with: new EventSource(API_BASE_URL + '/stream')
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    async with SUBSCRIBERS_LOCK:
        SUBSCRIBERS.append(queue)

    async def close_on_disconnect():
        # watch for client disconnect and cleanup
        await request.is_disconnected()
        async with SUBSCRIBERS_LOCK:
            try:
                SUBSCRIBERS.remove(queue)
            except ValueError:
                pass

    # Spawn task to cleanup on disconnect
    asyncio.create_task(close_on_disconnect())

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # for some proxies
    }
    return StreamingResponse(sse_event_generator(queue), media_type="text/event-stream", headers=headers)
