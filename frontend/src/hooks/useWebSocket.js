import { useRef, useState, useCallback, useEffect } from 'react';

export default function useWebSocket() {
  const wsRef = useRef(null);
  const [connected, setConnected] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const onMessageRef = useRef(null);

  const connect = useCallback(() => {
    return new Promise((resolve, reject) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const ws = new WebSocket(`${protocol}//${host}/ws/track_simple`);

      ws.onopen = () => {
        wsRef.current = ws;
        setConnected(true);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'session_created') {
          setSessionId(data.session_id);
          resolve(data.session_id);
        }
        if (onMessageRef.current) {
          onMessageRef.current(data);
        }
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        reject(err);
      };

      ws.onclose = () => {
        wsRef.current = null;
        setConnected(false);
        setSessionId(null);
      };
    });
  }, []);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      try {
        wsRef.current.send(JSON.stringify({ type: 'end' }));
      } catch (e) {
        // ignore
      }
      wsRef.current.close();
    }
  }, []);

  const sendFrame = useCallback((base64Frame, width, height) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'frame',
        frame: base64Frame,
        width,
        height,
      }));
    }
  }, []);

  const sendMessage = useCallback((msg) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const setOnMessage = useCallback((handler) => {
    onMessageRef.current = handler;
  }, []);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return { connect, disconnect, sendFrame, sendMessage, setOnMessage, connected, sessionId };
}
