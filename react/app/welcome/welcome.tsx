import React, { useState, useEffect } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';

export const Welcome = () => {
  const socketUrl = 'ws://localhost:8000/ws/1';

  const [messageHistory, setMessageHistory] = useState([]);

  const {
    sendMessage,
    lastMessage,
    readyState,
  } = useWebSocket(socketUrl, {
    shouldReconnect: (closeEvent) => true, 
    reconnectAttempts: 10,
    reconnectInterval: 3000,
  });

  // update message list
  useEffect(() => {
    if (lastMessage !== null) {
      setMessageHistory((prev) => prev.concat(lastMessage.data));
    }
  }, [lastMessage]);

  // send message
  const handleClickSendMessage = () => {
    sendMessage('Hello from React!');
  };

  // connection status
  const connectionStatus = {
    [ReadyState.CONNECTING]: 'Connecting',
    [ReadyState.OPEN]: 'Open',
    [ReadyState.CLOSING]: 'Closing',
    [ReadyState.CLOSED]: 'Closed',
    [ReadyState.UNINSTANTIATED]: 'Uninstantiated',
  }[readyState];

  return (
    <div style={{ padding: 20 }}>
      <h2>FastAPI + React WebSocket</h2>
      
      <div>Status: <strong>{connectionStatus}</strong></div>
      
      <button 
        onClick={handleClickSendMessage} 
        disabled={readyState !== ReadyState.OPEN}
        style={{ marginTop: 10 }}
      >
        Send Message to Agent
      </button>

      {/* message list */}
      <h3>Received Messages:</h3>
      <ul>
        {messageHistory.map((message, idx) => (
          <li key={idx}>{message}</li>
        ))}
      </ul>
    </div>
  );
};