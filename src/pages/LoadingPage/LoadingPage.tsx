import { Alert, Box, Card, CardContent, Stack, Typography } from '@mui/material';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { generateMoodPlaylist } from '../../entities/playlist/api/mockPlaylistApi';
import { useMusicMoodStore } from '../../shared/model/musicStore';
import { AppButton } from '../../shared/ui/AppButton/AppButton';
import { Loader } from '../../shared/ui/Loader/Loader';
import { Layout } from '../../widgets/Layout/Layout';

export const LoadingPage = () => {
  const navigate = useNavigate();
  const moodInput = useMusicMoodStore((state) => state.moodInput);
  const setCurrentPlaylist = useMusicMoodStore((state) => state.setCurrentPlaylist);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const hasStartedRef = useRef(false);

  const analyzeMood = useCallback(async () => {
    setIsLoading(true);
    setError('');

    try {
      const playlist = await generateMoodPlaylist(moodInput);
      setCurrentPlaylist(playlist);
      navigate('/result', { replace: true });
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : 'Неожиданная ошибка анализа.';
      setError(message);
      setIsLoading(false);
    }
  }, [moodInput, navigate, setCurrentPlaylist]);

  useEffect(() => {
    if (hasStartedRef.current) {
      return;
    }

    hasStartedRef.current = true;
    void analyzeMood();
  }, [analyzeMood]);

  return (
    <Layout>
      <Box sx={{ width: 'min(620px, 100%)', mx: 'auto', pt: { xs: 2, md: 6 } }}>
        <Card>
          <CardContent>
            {isLoading ? (
              <Loader />
            ) : (
              <Stack spacing={3} sx={{ textAlign: 'center' }}>
                <Typography variant="h5" sx={{ fontWeight: 850 }}>
                  Анализ остановлен
                </Typography>
                <Alert severity="error">{error}</Alert>
                <Stack
                  direction={{ xs: 'column', sm: 'row' }}
                  spacing={1.5}
                  sx={{ justifyContent: 'center' }}
                >
                  <AppButton onClick={() => void analyzeMood()}>Попробовать ещё раз</AppButton>
                  <AppButton variant="outlined" onClick={() => navigate('/capture')}>
                    Изменить ввод
                  </AppButton>
                </Stack>
              </Stack>
            )}
          </CardContent>
        </Card>
      </Box>
    </Layout>
  );
};
