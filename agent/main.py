import os
import asyncio
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from connection_manager import manager
from agent_service import calendar_agent, CalendarDeps
import uvicorn
from text_audio import audio2text, text2audio
from pydantic_ai.messages import ModelMessage
import agent_tools


# import debugpy
# debugpy.listen(("0.0.0.0", 5678))
# print("Waiting for debugger attach...")
# debugpy.wait_for_client()

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
    deps = CalendarDeps()
    message_history: list[ModelMessage] = []
    try:
        if not await ensure_env(websocket, ["OPENAI_API_KEY"]):
            return
        while True:
            # receive message from client
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "text" in message and message["text"] is not None:
                data = message["text"]

                try:
                    result = await calendar_agent.run(data, deps=deps, message_history=message_history)
                except Exception as exc:
                    await manager.send_personal_message(f"Agent 运行失败: {exc}", websocket)
                    continue

                response = getattr(result, "data", None)
                if response is None:
                    response = getattr(result, "output", None)
                if response is None:
                    response = str(result)
                message_history = result.all_messages()
                response_text = str(response)
                await manager.send_personal_message(response_text, websocket)
                try:
                    audio_bytes = await text2audio(response_text)
                    await manager.send_personal_bytes(audio_bytes, websocket)
                except Exception as exc:
                    await manager.send_personal_message(f"语音合成失败: {exc}", websocket)
            elif "bytes" in message and message["bytes"] is not None:
                await manager.send_personal_message("语音请使用 /ws-audio 通道。", websocket)
            
            
    finally:
        message_history.clear()
        if websocket in manager.active_connections:
            manager.disconnect(websocket)
        print(f"user #{client_id} leave")


@app.websocket("/ws-audio/{client_id}")
async def websocket_audio_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)
    deps = CalendarDeps()
    message_history: list[ModelMessage] = []
    try:
        if not await ensure_env(websocket, ["OPENAI_API_KEY", "GROQ_API_KEY"]):
            return
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "text" in message and message["text"] is not None:
                text = message["text"]
            elif "bytes" in message and message["bytes"] is not None:
                data_bytes = message["bytes"]
                try:
                    text = await asyncio.to_thread(audio2text, data_bytes)
                except Exception as exc:
                    await manager.send_personal_message(f"语音转文字失败: {exc}", websocket)
                    continue
            else:
                continue

            if not text:
                await manager.send_personal_message("没有识别到可用的语音内容。", websocket)
                continue

            try:
                result = await calendar_agent.run(text, deps=deps, message_history=message_history)
            except Exception as exc:
                await manager.send_personal_message(f"Agent 运行失败: {exc}", websocket)
                continue

            response = getattr(result, "data", None)
            if response is None:
                response = getattr(result, "output", None)
            if response is None:
                response = str(result)
            message_history = result.all_messages()
            response_text = str(response)
            await manager.send_personal_message(response_text, websocket)
            try:
                audio_bytes = await text2audio(response_text)
                await manager.send_personal_bytes(audio_bytes, websocket)
            except Exception as exc:
                await manager.send_personal_message(f"语音合成失败: {exc}", websocket)
    finally:
        message_history.clear()
        if websocket in manager.active_connections:
            manager.disconnect(websocket)
        print(f"voice user #{client_id} leave")



async def ensure_env(websocket: WebSocket, keys: list[str]) -> bool:
    missing = [key for key in keys if not os.getenv(key)]
    if not missing:
        return True
    missing_text = ", ".join(missing)
    await manager.send_personal_message(f"缺少 {missing_text}，请先配置 .env。", websocket)
    try:
        await websocket.close()
    except Exception:
        pass
    return False


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
