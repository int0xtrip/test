import { useRef, useState, useCallback, useEffect } from 'react';

export default function useWebcam() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState(null);

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          frameRate: { ideal: 30, min: 15 },
          facingMode: 'user',
        },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setActive(true);
      setError(null);
    } catch (err) {
      setError('Camera access denied. Please allow camera access.');
      console.error('Webcam error:', err);
    }
  }, []);

  const stop = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    setActive(false);
  }, []);

  const captureFrame = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !active) return null;

    const ctx = canvas.getContext('2d');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    ctx.drawImage(video, 0, 0);

    const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
    const base64 = dataUrl.split(',')[1];
    return {
      base64,
      width: canvas.width,
      height: canvas.height,
    };
  }, [active]);

  useEffect(() => {
    return () => stop();
  }, [stop]);

  return { videoRef, canvasRef, start, stop, captureFrame, active, error };
}
