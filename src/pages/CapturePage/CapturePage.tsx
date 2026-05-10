import { Alert, Stack, Typography } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Camera } from '../../features/capture/ui/Camera';
import { MoodTextInput } from '../../features/capture/ui/MoodTextInput';
import { AppButton } from '../../shared/ui/AppButton/AppButton';
import { useMusicMoodStore } from '../../shared/model/musicStore';
import { Layout } from '../../widgets/Layout/Layout';
import styles from './CapturePage.module.css';

type CameraStatus = 'pending' | 'available' | 'unavailable';

export const CapturePage = () => {
  const navigate = useNavigate();
  const preferences = useMusicMoodStore((state) => state.preferences);
  const setMoodInput = useMusicMoodStore((state) => state.setMoodInput);
  const [text, setText] = useState('');
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [cameraStatus, setCameraStatus] = useState<CameraStatus>(
    preferences.cameraEnabled ? 'pending' : 'unavailable',
  );
  const [error, setError] = useState('');

  const textRequired = useMemo(
    () => !preferences.cameraEnabled || cameraStatus === 'unavailable',
    [cameraStatus, preferences.cameraEnabled],
  );

  const handleCameraAvailabilityChange = useCallback((available: boolean) => {
    setCameraStatus(available ? 'available' : 'unavailable');
  }, []);

  const handleAnalyze = () => {
    if (textRequired && !text.trim()) {
      setError('Опишите, что вы чувствуете, чтобы продолжить в текстовом режиме.');
      return;
    }

    setError('');
    setMoodInput({
      text: text.trim(),
      hasCameraCapture: Boolean(capturedImage),
    });
    navigate('/loading');
  };

  return (
    <Layout>
      <Stack spacing={3}>
        <div>
          <Typography variant="overline" color="primary" sx={{ fontWeight: 900 }}>
            Шаг 2
          </Typography>
          <Typography variant="h2" sx={{ fontSize: { xs: '2.2rem', md: '3.4rem' } }}>
            Зафиксируйте настроение
          </Typography>
          <Typography sx={{ mt: 1, maxWidth: 680, color: 'text.secondary' }}>
            Сделайте быстрый снимок, добавьте короткое описание или объедините оба способа для более точного подбора.
          </Typography>
        </div>
        <div className={styles.grid}>
          <Camera
            enabled={preferences.cameraEnabled}
            onCaptureChange={setCapturedImage}
            onCameraAvailabilityChange={handleCameraAvailabilityChange}
          />
          <Stack className={styles.panel} spacing={3}>
            <MoodTextInput value={text} required={textRequired} error={error} onChange={setText} />
            {error ? <Alert severity="error">{error}</Alert> : null}
            <AppButton disabled={textRequired && !text.trim()} onClick={handleAnalyze}>
              Анализировать настроение
            </AppButton>
          </Stack>
        </div>
      </Stack>
    </Layout>
  );
};
