import { Stack, TextField, Typography } from '@mui/material';

type MoodTextInputProps = {
  value: string;
  required: boolean;
  error?: string;
  onChange: (value: string) => void;
};

export const MoodTextInput = ({ value, required, error, onChange }: MoodTextInputProps) => {
  return (
    <Stack spacing={1.5}>
      <div>
        <Typography variant="h6" sx={{ fontWeight: 850 }}>
          Расскажите, как вы себя чувствуете
        </Typography>
        <Typography color="text.secondary">
          Подсказки: как прошёл ваш день? Что вы сейчас чувствуете?
        </Typography>
      </div>
      <TextField
        multiline
        minRows={5}
        value={value}
        required={required}
        error={Boolean(error)}
        helperText={error || (required ? 'Обязательно в текстовом режиме.' : 'Необязательно, если доступен снимок с камеры.')}
        placeholder="Я чувствую спокойствие после долгого дня, но хочется чего-то тёплого и бодрящего..."
        onChange={(event) => onChange(event.target.value)}
      />
    </Stack>
  );
};
