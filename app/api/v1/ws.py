"""WebSocket activity feed — real-time event streaming via Redis pub/sub."""

import asyncio
import json
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

ACTIVITY_CHANNEL = "activity:events"

# Active WebSocket connections
active_connections: Set[WebSocket] = set()


async def broadcast_activity(agent_type: str, action: str, summary: str, level: str = "info"):
    """Send activity event to all connected WebSocket clients."""
    message = json.dumps({
        "agent_type": agent_type,
        "action": action,
        "summary": summary,
        "level": level,
    })
    dead: list[WebSocket] = []
    for ws in active_connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        active_connections.discard(ws)


async def listen_redis():
    """Background task: listen to Redis pub/sub and broadcast to WebSockets."""
    from app.core.redis_client import get_redis
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(ACTIVITY_CHANNEL)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await broadcast_activity(
                        data.get("agent_type", ""),
                        data.get("action", ""),
                        data.get("summary", ""),
                        data.get("level", "info"),
                    )
                except json.JSONDecodeError:
                    pass
    except asyncio.CancelledError:
        await pubsub.unsubscribe(ACTIVITY_CHANNEL)
        await pubsub.close()


@router.websocket("/ws/activity")
async def activity_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time activity streaming."""
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            # Keep connection alive and handle client messages
            data = await websocket.receive_text()
            # Client can send ping to keep alive
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        active_connections.discard(websocket)
