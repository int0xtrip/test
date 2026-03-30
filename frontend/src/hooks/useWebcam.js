import { useRef, useState, useCallback, useEffect } from 'react';

export default function useWebcam() {
  const videoRef    = useRef(null);
  const canvasRef   = useRef(null);
  const streamRef   = useRef(null);
  const [active, setActive] = useState(false);
  const [error,  setError]  = useState(null);

  // Callback ref — React calls this the instant the <video> element mounts.
  // This guarantees the stream is connected even when getUserMedia() completed
  // *before* WebcamView was rendered (the usual case, because tracking state
  // drives rendering and is set after start() returns).
  const videoCallbackRef = useCallback((node) => {
    videoRef.current = node;
    if (node && streamRef.current) {
      node.srcObject = streamRef.current;
      node.play().catch(() => {});
    }
  }, []);

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width:  { ideal: 640 },
          height: { ideal: 480 },
          frameRate: { ideal: 30, min: 15 },
          facingMode: 'user',
        },
        audio: false,
      });
      streamRef.current = stream;

      // If the element is already mounted (edge case), connect right away.
      // Otherwise videoCallbackRef handles it when the element mounts.
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      setActive(true);
      setError(null);
    } catch (err) {
      setError('Camera access denied. Please allow camera access and reload.');
      console.error('Webcam error:', err);
    }
  }, []);

  const stop = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setActive(false);
  }, []);

  const captureFrame = useCallback(() => {
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !active) return null;

    const ctx = canvas.getContext('2d');
    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 480;
    ctx.drawImage(video, 0, 0);

    const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
    return {
      base64: dataUrl.split(',')[1],
      width:  canvas.width,
      height: canvas.height,
    };
  }, [active]);

  useEffect(() => () => stop(), [stop]);

  return {
    videoRef: videoCallbackRef,  // callback ref keeps timing-safe
    canvasRef,
    start, stop, captureFrame,
    active, error,
  };
}
