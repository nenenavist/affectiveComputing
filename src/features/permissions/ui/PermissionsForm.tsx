import { Alert, Card, CardContent, Stack, Typography } from '@mui/material';
import { useState } from 'react';
import { CheckboxGroup } from '../../../shared/ui/CheckboxGroup/CheckboxGroup';
import { AppButton } from '../../../shared/ui/AppButton/AppButton';

type PermissionsFormProps = {
  initialCameraEnabled: boolean;
  initialConsent: boolean;
  onContinue: (values: { cameraEnabled: boolean; consentToProcessing: boolean }) => void;
};

export const PermissionsForm = ({
  initialCameraEnabled,
  initialConsent,
  onContinue,
}: PermissionsFormProps) => {
  const [cameraEnabled, setCameraEnabled] = useState(initialCameraEnabled);
  const [consentToProcessing, setConsentToProcessing] = useState(initialConsent);
  const [error, setError] = useState('');

  const handleContinue = () => {
    if (cameraEnabled && !consentToProcessing) {
      setError('При включённой камере нужно согласие на обработку изображения.');
      return;
    }

    setError('');
    onContinue({ cameraEnabled, consentToProcessing });
  };

  return (
    <Card>
      <CardContent>
        <Stack spacing={3}>
          <div>
            <Typography variant="h4">Выберите режим анализа</Typography>
            <Typography sx={{ mt: 1, color: 'text.secondary' }}>
              Камера добавит визуальный сигнал. Вы также можете продолжить только с текстовым вводом.
            </Typography>
          </div>
          <CheckboxGroup
            options={[
              {
                id: 'camera',
                label: 'Разрешить доступ к камере',
                checked: cameraEnabled,
                onChange: setCameraEnabled,
              },
              {
                id: 'consent',
                label: 'Согласие на обработку изображения',
                checked: consentToProcessing,
                onChange: setConsentToProcessing,
              },
            ]}
          />
          {error ? <Alert severity="error">{error}</Alert> : null}
          {!cameraEnabled ? (
            <Alert severity="info">Текстовый режим доступен без разрешения камеры.</Alert>
          ) : null}
          <AppButton onClick={handleContinue}>Продолжить</AppButton>
        </Stack>
      </CardContent>
    </Card>
  );
};
