import React, { useState, useEffect, useRef, useCallback } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';

export const Welcome = () => {
  const socketUrl = 'ws://localhost:8000/ws/1';
  const audioSocketUrl = 'ws://localhost:8000/ws-audio/1';

  const [messageHistory, setMessageHistory] = useState([]);
  const [testMessage, setTestMessage] = useState('');
  const [isVoiceMode, setIsVoiceMode] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isAwaitingResponse, setIsAwaitingResponse] = useState(false);
  const [isAudioPlaying, setIsAudioPlaying] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const messageListRef = useRef<HTMLUListElement | null>(null);
  const activeAudioCountRef = useRef(0);
  const hasSentHelloRef = useRef(false);

  const {
    sendMessage,
    lastMessage,
    readyState,
  } = useWebSocket(socketUrl, {
    shouldReconnect: (closeEvent) => true, 
    reconnectAttempts: 10,
    reconnectInterval: 3000,
  });

  const {
    sendMessage: sendAudioMessage,
    lastMessage: lastAudioMessage,
    readyState: audioReadyState,
  } = useWebSocket(audioSocketUrl, {
    shouldReconnect: () => true,
    reconnectAttempts: 10,
    reconnectInterval: 3000,
    queryParams: {
      binaryType: 'arraybuffer',
    },
  }, isVoiceMode);

  // update message list
  useEffect(() => {
    if (lastMessage !== null) {
      setMessageHistory((prev) => prev.concat(lastMessage.data));
      setIsAwaitingResponse(false);
    }
  }, [lastMessage]);

  // play audio from the agent
  useEffect(() => {
    if (lastAudioMessage === null) {
      return;
    }

    const data = lastAudioMessage.data;
    if (data instanceof Blob || data instanceof ArrayBuffer) {
      const audioBlob = data instanceof Blob ? data : new Blob([data], { type: 'audio/mpeg' });
      const normalizedBlob = audioBlob.type ? audioBlob : new Blob([audioBlob], { type: 'audio/mpeg' });
      const audioUrl = URL.createObjectURL(normalizedBlob);
      const audio = new Audio(audioUrl);
      activeAudioCountRef.current += 1;
      setIsAudioPlaying(true);
      const handleAudioDone = () => {
        activeAudioCountRef.current = Math.max(0, activeAudioCountRef.current - 1);
        if (activeAudioCountRef.current === 0) {
          setIsAudioPlaying(false);
        }
      };
      audio.onended = handleAudioDone;
      audio.onerror = handleAudioDone;
      audio.onpause = handleAudioDone;
      audio.play()
        .catch(handleAudioDone)
        .finally(() => URL.revokeObjectURL(audioUrl));
      setIsAwaitingResponse(false);
    } else { 
      setMessageHistory((prev) => prev.concat(data));
      setIsAwaitingResponse(false);
    }
  }, [lastAudioMessage]);

  // scroll to bottom on new message
  useEffect(() => {
    if (messageListRef.current) {
      messageListRef.current.scrollTo({
        top: messageListRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [messageHistory]);

  // send message
  const handleClickSendMessage = () => {
    const value = testMessage.trim();
    if (!value) {
      return;
    }
    setIsAwaitingResponse(true);
    sendMessage(value);
  };

  const stopRecording = useCallback(() => {
    if (!isRecording) {
      return;
    }
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  }, [isRecording]);

  const startRecording = useCallback(async () => {
    if (isRecording || isAudioPlaying) {
      return;
    }

    if (audioReadyState !== ReadyState.OPEN || !navigator.mediaDevices?.getUserMedia) {
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      const preferredMimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : '';
      const recorder = preferredMimeType
        ? new MediaRecorder(stream, { mimeType: preferredMimeType })
        : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      // save audio data chunks
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const mimeType = recorder.mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        sendAudioMessage(audioBlob);
        mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        setIsAwaitingResponse(true);
      };

      recorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error('microphone error:', error);
    }
  }, [audioReadyState, isAudioPlaying, isRecording, sendAudioMessage])

  useEffect(() => {
    if (!isVoiceMode && isRecording) {
      stopRecording();
    }
  }, [isVoiceMode, isRecording, stopRecording]);

  // send initial hello in voice mode
  useEffect(() => {
    if (!isVoiceMode || audioReadyState !== ReadyState.OPEN || hasSentHelloRef.current) {
      return;
    }
    sendAudioMessage('hello');
    hasSentHelloRef.current = true;
  }, [audioReadyState, isVoiceMode, sendAudioMessage]);


  // connection status
  const connectionStatus = {
    [ReadyState.CONNECTING]: 'Connecting',
    [ReadyState.OPEN]: 'Open',
    [ReadyState.CLOSING]: 'Closing',
    [ReadyState.CLOSED]: 'Closed',
    [ReadyState.UNINSTANTIATED]: 'Uninstantiated',
  }[readyState];
  const audioConnectionStatus = {
    [ReadyState.CONNECTING]: 'Connecting',
    [ReadyState.OPEN]: 'Open',
    [ReadyState.CLOSING]: 'Closing',
    [ReadyState.CLOSED]: 'Closed',
    [ReadyState.UNINSTANTIATED]: 'Uninstantiated',
  }[audioReadyState];

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_12%_18%,rgba(217,121,68,0.18),transparent_55%),radial-gradient(circle_at_82%_0%,rgba(31,27,22,0.12),transparent_50%),linear-gradient(160deg,#f6f2ea_0%,#f3ede5_48%,#efe4d7_100%)] text-[#1f1b16] flex items-center justify-center px-5 py-12">
      <div className="relative w-full max-w-240 overflow-hidden rounded-[28px] border border-[#e6dacd] bg-[#fff8f0] px-6 py-8 shadow-[0_30px_80px_rgba(31,27,22,0.18)] sm:px-10 sm:py-10">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_88%_30%,rgba(217,121,68,0.15),transparent_55%),radial-gradient(circle_at_12%_80%,rgba(31,27,22,0.08),transparent_55%)]" />

        <header className="relative z-10 mb-6 flex flex-col gap-2 animate-[welcome-rise_700ms_ease_forwards]">
          <div className="text-[11px] uppercase tracking-[0.28em] text-[#6f6258] font-[Trebuchet_MS,Lucida_Sans,sans-serif]">Realtime Voice</div>
          <h1 className="text-[clamp(32px,3.4vw,48px)] font-semibold">Google Calendar Agent</h1>
          <p className="text-[15px] text-[#6f6258]">用语音驱动日程，实时把想法变成安排。</p>
        </header>

        <div className="relative z-10 mb-6 inline-flex items-center gap-2 rounded-full border border-[#f1d2bd] bg-[#fff1e4] px-4 py-2 text-sm font-[Trebuchet_MS,Lucida_Sans,sans-serif] animate-[welcome-rise_700ms_ease_forwards]">
          <span
            className={`h-2.5 w-2.5 rounded-full shadow-[0_0_0_4px_rgba(193,183,175,0.25)] ${
              readyState === ReadyState.OPEN
                ? 'bg-[#27a66c] shadow-[0_0_0_4px_rgba(39,166,108,0.25)]'
                : readyState === ReadyState.CONNECTING
                  ? 'bg-[#e2a024] shadow-[0_0_0_4px_rgba(226,160,36,0.25)]'
                  : readyState === ReadyState.CLOSED
                    ? 'bg-[#d14f3f] shadow-[0_0_0_4px_rgba(209,79,63,0.25)]'
                    : 'bg-[#c1b7af]'
            }`}
          />
          <span>WebSocket {connectionStatus}</span>
        </div>
        <div className="relative z-10 mb-6 inline-flex items-center gap-2 rounded-full border border-[#e2d6c9] bg-[#fff4ea] px-4 py-2 text-sm font-[Trebuchet_MS,Lucida_Sans,sans-serif] animate-[welcome-rise_700ms_ease_forwards]">
          <span
            className={`h-2.5 w-2.5 rounded-full shadow-[0_0_0_4px_rgba(193,183,175,0.25)] ${
              audioReadyState === ReadyState.OPEN
                ? 'bg-[#27a66c] shadow-[0_0_0_4px_rgba(39,166,108,0.25)]'
                : audioReadyState === ReadyState.CONNECTING
                  ? 'bg-[#e2a024] shadow-[0_0_0_4px_rgba(226,160,36,0.25)]'
                  : audioReadyState === ReadyState.CLOSED
                    ? 'bg-[#d14f3f] shadow-[0_0_0_4px_rgba(209,79,63,0.25)]'
                    : 'bg-[#c1b7af]'
            }`}
          />
          <span>Voice WS {audioConnectionStatus}</span>
        </div>

        <div className="relative z-10 mb-7 grid gap-4 font-[Trebuchet_MS,Lucida_Sans,sans-serif] animate-[welcome-rise_700ms_ease_forwards]">
          <div className="flex flex-wrap items-center gap-3 rounded-[18px] border border-[#e6dacd] bg-[#fffdf8] px-4 py-3 shadow-[0_10px_30px_rgba(31,27,22,0.08)]">
            <label className="text-xs uppercase tracking-[0.22em] text-[#6f6258]">Test Message</label>
            <input
              className="min-w-55 flex-1 bg-transparent text-sm text-[#1f1b16] placeholder:text-[#8b7c72] focus:outline-none"
              placeholder="输入要发送的内容..."
              value={testMessage}
              onChange={(event) => setTestMessage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  handleClickSendMessage();
                }
              }}
            />
            <button
              className="cursor-pointer rounded-full border border-[#e6dacd] bg-transparent px-5 py-2 text-xs font-semibold text-[#1f1b16] transition hover:-translate-y-0.5 hover:shadow-[0_10px_24px_rgba(31,27,22,0.12)] disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none disabled:transform-none"
              onClick={handleClickSendMessage}
              disabled={readyState !== ReadyState.OPEN || !testMessage.trim() || isAwaitingResponse}
            >
              发送
            </button>
          </div>
          <button
            className={`cursor-pointer rounded-full border border-transparent px-6 py-3 text-sm font-semibold text-[#fffaf6] transition hover:-translate-y-0.5 hover:shadow-[0_18px_30px_rgba(178,79,46,0.32)] disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none disabled:transform-none ${
              isVoiceMode
                ? 'bg-[linear-gradient(120deg,#d14f3f,#9e2e22)] shadow-[0_12px_24px_rgba(178,79,46,0.28)]'
                : 'bg-[linear-gradient(120deg,#d97944,#b24f2e)] shadow-[0_12px_24px_rgba(178,79,46,0.28)]'
            }`}
            onClick={() => setIsVoiceMode((prev) => !prev)}
            disabled={isAwaitingResponse && !isVoiceMode}
          >
            {isVoiceMode ? '结束语音对话' : '开始语音对话'}
          </button>
          {isVoiceMode && (
            <button
              className={`select-none rounded-[18px] border border-[#e6dacd] px-6 py-4 text-sm font-semibold transition ${
                isRecording
                  ? 'bg-[#d14f3f] text-[#fffaf6] shadow-[0_18px_30px_rgba(178,79,46,0.32)]'
                  : 'bg-[#fff1e4] text-[#1f1b16] shadow-[0_10px_24px_rgba(31,27,22,0.12)]'
              } ${
                audioReadyState !== ReadyState.OPEN || isAwaitingResponse || isAudioPlaying
                  ? 'cursor-not-allowed opacity-60 grayscale'
                  : 'hover:-translate-y-0.5 hover:shadow-[0_18px_30px_rgba(178,79,46,0.24)]'
              }`}
              onPointerDown={startRecording}
              onPointerUp={stopRecording}
              onPointerLeave={stopRecording}
              onPointerCancel={stopRecording}
              disabled={audioReadyState !== ReadyState.OPEN || isAwaitingResponse || isAudioPlaying}
              title={
                audioReadyState !== ReadyState.OPEN
                  ? '语音连接中，稍候再试'
                  : isAwaitingResponse
                    ? '等待回复中，暂时不能说话'
                    : isAudioPlaying
                      ? '正在播放语音，结束后可继续说话'
                      : '按住开始录音，松开发送'
              }
            >
              {isRecording ? '松开发送' : '按住说话'}
            </button>
          )}
        </div>

        <section className="relative z-10 rounded-[20px] border border-[#e6dacd] bg-[#fffdf8] px-5 py-5 font-[Trebuchet_MS,Lucida_Sans,sans-serif] animate-[welcome-rise_700ms_ease_forwards]">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold">Received Messages</h3>
            <span className="rounded-full bg-[#f3e1d3] px-2.5 py-1 text-xs text-[#6f6258]">{messageHistory.length}</span>
          </div>
          <ul ref={messageListRef} className="grid max-h-65 gap-2.5 overflow-auto">
            {messageHistory.length === 0 && (
              <li className="rounded-[14px] border border-[#f0d9c7] bg-[#fff6ee] px-3.5 py-2.5 text-sm italic text-[#6f6258] animate-[welcome-fade_420ms_ease_both]">
                等待来自 Agent 的回复…
              </li>
            )}
            {messageHistory.map((message, idx) => (
              <li className="rounded-[14px] border border-[#f0d9c7] bg-[#fff6ee] px-3.5 py-2.5 text-sm text-[#1f1b16] animate-[welcome-fade_420ms_ease_both]" key={idx}>
                {message}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
};
