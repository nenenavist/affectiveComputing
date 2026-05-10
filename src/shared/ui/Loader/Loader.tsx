import { Box, CircularProgress, Skeleton, Stack, Typography } from '@mui/material';

type LoaderProps = {
  title?: string;
  description?: string;
};

export const Loader = ({
  title = 'Анализируем ваше настроение...',
  description = 'Подбираем музыкальную палитру под ваше эмоциональное состояние.',
}: LoaderProps) => {
  return (
    <Box sx={{ textAlign: 'center' }}>
      <CircularProgress size={58} thickness={4} />
      <Typography variant="h5" sx={{ mt: 3, fontWeight: 800 }}>
        {title}
      </Typography>
      <Typography sx={{ mt: 1, color: 'text.secondary' }}>
        {description}
      </Typography>
      <Stack spacing={1.5} sx={{ mt: 4 }}>
        <Skeleton variant="rounded" height={72} sx={{ borderRadius: 4 }} />
        <Skeleton variant="rounded" height={72} sx={{ borderRadius: 4 }} />
        <Skeleton variant="rounded" height={72} sx={{ borderRadius: 4 }} />
      </Stack>
    </Box>
  );
};
