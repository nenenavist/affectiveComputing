import { Alert, Button, Stack, Typography } from '@mui/material';
import { useCallback, useEffect, useRef, useState } from 'react';
import styles from './Camera.module.css';

type CameraProps = {
  enabled: boolean;
  onCaptureChange: (image: string | null) => void;
  onCameraAvailabilityChange: (available: boolean) => void;
};

export const Camera = ({ enabled, onCaptureChange, onCameraAvailabilityChange }: CameraProps) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const countdownTimerRef = useRef<number | null>(null);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [cameraReady, setCameraReady] = useState(false);
  const [error, setError] = useState('');

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setCameraReady(false);
  }, []);

  const startCamera = useCallback(async () => {
    if (!enabled || capturedImage) {
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Этот браузер не поддерживает камеру. Используйте текстовый ввод.');
      onCameraAvailabilityChange(false);
      return;
    }

    try {
      setError('');
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user' },
        audio: false,
      });

      streamRef.current = mediaStream;

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }

      setCameraReady(true);
      onCameraAvailabilityChange(true);
    } catch {
      setError('Доступ к камере отклонён. Вы всё равно можете продолжить в текстовом режиме.');
      onCameraAvailabilityChange(false);
      stopCamera();
    }
  }, [capturedImage, enabled, onCameraAvailabilityChange, stopCamera]);

  useEffect(() => {
    if (!enabled) {
      stopCamera();
      onCameraAvailabilityChange(false);
      return undefined;
    }

    void startCamera();

    return () => {
      stopCamera();
      if (countdownTimerRef.current) {
        window.clearInterval(countdownTimerRef.current);
      }
    };
  }, [enabled, onCameraAvailabilityChange, startCamera, stopCamera]);

  const captureFrame = () => {
    const video = videoRef.current;

    if (!video) {
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const context = canvas.getContext('2d');

    if (!context) {
      return;
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const image = canvas.toDataURL('image/jpeg', 0.86);
    setCapturedImage(image);
    onCaptureChange(image);
    stopCamera();
  };

  const handleCapture = () => {
    if (!cameraReady || countdown !== null) {
      return;
    }

    setCountdown(3);
    let nextValue = 3;
    countdownTimerRef.current = window.setInterval(() => {
      nextValue -= 1;

      if (nextValue === 0) {
        if (countdownTimerRef.current) {
          window.clearInterval(countdownTimerRef.current);
        }
        setCountdown(null);
        captureFrame();
        return;
      }

      setCountdown(nextValue);
    }, 1000);
  };

  const handleRetake = () => {
    setCapturedImage(null);
    onCaptureChange(null);
    void startCamera();
  };

  if (!enabled) {
    return (
      <div className={styles.placeholder}>
        <Stack spacing={1}>
          <Typography variant="h5" sx={{ fontWeight: 850 }}>
            Текстовый режим
          </Typography>
          <Typography>Камера отключена. Напишите пару слов о своём дне, чтобы подобрать настроение.</Typography>
        </Stack>
      </div>
    );
  }

  return (
    <Stack spacing={2}>
      <div className={styles.cameraCard}>
        {capturedImage ? (
          <img className={styles.captured} src={capturedImage} alt="Снимок настроения" />
        ) : (
          <video ref={videoRef} className={styles.preview} autoPlay muted playsInline />
        )}
        {capturedImage ? (
          <div className={styles.topActions}>
            <Button variant="contained" color="secondary" onClick={handleRetake}>
              Переснять
            </Button>
          </div>
        ) : null}
        {!capturedImage ? (
          <div className={styles.controls}>
            <button
              className={styles.captureButton}
              type="button"
              onClick={handleCapture}
              disabled={!cameraReady || countdown !== null}
              aria-label="Сделать снимок"
            />
          </div>
        ) : null}
        {countdown !== null ? <div className={styles.countdown}>{countdown}</div> : null}
      </div>
      {error ? <Alert severity="warning">{error}</Alert> : null}
    </Stack>
  );
};
