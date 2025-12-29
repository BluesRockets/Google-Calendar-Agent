import os
from io import BytesIO
from groq import Groq
import edge_tts

def audio2text(data_bytes: bytes) -> str:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    audio_file = BytesIO(data_bytes)
    audio_file.name = "audio.webm"
    model = os.getenv("GROQ_STT_MODEL", "whisper-large-v3")
    transcription = client.audio.transcriptions.create(
        file=audio_file,
        model=model,
        response_format="text",
        temperature=0,
    )
    if isinstance(transcription, str):
        return transcription.strip()
    text = getattr(transcription, "text", "") or ""
    return text.strip()


async def text2audio(text: str) -> bytes:
    voice = os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural")
    communicate = edge_tts.Communicate(text, voice)
    audio_chunks = []
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            audio_chunks.append(chunk.get("data", b""))
    return b"".join(audio_chunks)