import { Box, Stack, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { PermissionsForm } from '../../features/permissions/ui/PermissionsForm';
import { useMusicMoodStore } from '../../shared/model/musicStore';
import { Layout } from '../../widgets/Layout/Layout';

export const PermissionsPage = () => {
  const navigate = useNavigate();
  const preferences = useMusicMoodStore((state) => state.preferences);
  const setPreferences = useMusicMoodStore((state) => state.setPreferences);

  return (
    <Layout>
      <Box sx={{ width: 'min(680px, 100%)', mx: 'auto' }}>
        <Stack spacing={3}>
          <div>
            <Typography variant="overline" color="primary" sx={{ fontWeight: 900 }}>
              Шаг 1
            </Typography>
            <Typography variant="h2" sx={{ fontSize: { xs: '2.2rem', md: '3.4rem' } }}>
              Выберите способ ввода
            </Typography>
          </div>
          <PermissionsForm
            initialCameraEnabled={preferences.cameraEnabled}
            initialConsent={preferences.consentToProcessing}
            onContinue={(values) => {
              setPreferences(values);
              navigate('/capture');
            }}
          />
        </Stack>
      </Box>
    </Layout>
  );
};
