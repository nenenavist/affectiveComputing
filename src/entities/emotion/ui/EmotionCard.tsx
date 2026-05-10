import { AutoAwesomeRounded } from '@mui/icons-material';
import { Card, Stack, Typography } from '@mui/material';
import { motion } from 'framer-motion';
import { Emotion, emotionConfig } from '../model/types';
import styles from './EmotionCard.module.css';

type EmotionCardProps = {
  emotion: Emotion;
};

export const EmotionCard = ({ emotion }: EmotionCardProps) => {
  const config = emotionConfig[emotion];

  return (
    <motion.div
      initial={{ opacity: 0, y: 18, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
    >
      <Card className={styles.card} sx={{ background: config.background }}>
        <span className={styles.halo} style={{ backgroundColor: config.accent }} />
        <Stack className={styles.content} spacing={2.5}>
          <span className={styles.badge} style={{ backgroundColor: config.color }}>
            <AutoAwesomeRounded fontSize="small" />
            Настроение определено
          </span>
          <div>
            <Typography variant="h4" sx={{ color: config.color }}>
              {config.label}
            </Typography>
            <Typography sx={{ mt: 1, maxWidth: 480, color: 'text.secondary' }}>
              {config.description}
            </Typography>
          </div>
        </Stack>
      </Card>
    </motion.div>
  );
};
