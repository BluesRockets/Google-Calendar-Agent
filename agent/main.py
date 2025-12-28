from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from connectionManager import manager

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
                await manager.send_personal_message(f"you sent: {data}", websocket)
            elif "bytes" in message and message["bytes"] is not None:
                data_bytes = message["bytes"]
                size = len(data_bytes)
                await manager.send_personal_message(f"received bytes: {size}", websocket)
            
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"user #{client_id} leave")
