import os
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from connectionManager import manager
load_dotenv()
from tools import calendar_agent, CalendarDeps

app = FastAPI()

# --- CORS config ---
origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)
    try:
        while True:
            # receive message from client
            message = await websocket.receive()
            if "text" in message and message["text"] is not None:
                data = message["text"]
                if not os.getenv("OPENAI_API_KEY"):
                    await manager.send_personal_message("缺少 OPENAI_API_KEY，请先配置 .env。", websocket)
                    continue

                try:
                    result = await calendar_agent.run(data, deps=CalendarDeps())
                except Exception as exc:
                    await manager.send_personal_message(f"Agent 运行失败: {exc}", websocket)
                    continue

                response = getattr(result, "data", None)
                if response is None:
                    response = getattr(result, "output", None)
                if response is None:
                    response = str(result)
                await manager.send_personal_message(str(response), websocket)
            elif "bytes" in message and message["bytes"] is not None:
                data_bytes = message["bytes"]
                size = len(data_bytes)
                await manager.send_personal_message(f"received bytes: {size}", websocket)
            
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"user #{client_id} leave")
