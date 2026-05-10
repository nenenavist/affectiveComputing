import { Box, Typography } from '@mui/material';

type EmptyStateProps = {
  title: string;
  description?: string;
};

export const EmptyState = ({ title, description }: EmptyStateProps) => {
  return (
    <Box
      sx={{
        border: '1px dashed rgba(143, 123, 234, 0.34)',
        borderRadius: 4,
        p: 4,
        textAlign: 'center',
        backgroundColor: 'rgba(255, 255, 255, 0.54)',
      }}
    >
      <Typography variant="h6" sx={{ fontWeight: 800 }}>
        {title}
      </Typography>
      {description ? (
        <Typography sx={{ mt: 1, color: 'text.secondary' }}>
          {description}
        </Typography>
      ) : null}
    </Box>
  );
};
