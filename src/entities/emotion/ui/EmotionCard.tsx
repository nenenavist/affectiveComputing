import { AutoAwesomeRounded } from '@mui/icons-material';
import { Card, Stack, Typography } from '@mui/material';
import { motion } from 'framer-motion';
import { Emotion, emotionConfig } from '../model/types';
import styles from './EmotionCard.module.css';

type EmotionCardProps = {
  emotion: Emotion;
  emotionWeights?: Partial<Record<Emotion, number>>;
};

const emotions: Emotion[] = ['happy', 'sad', 'angry', 'neutral'];

export const EmotionCard = ({ emotion, emotionWeights }: EmotionCardProps) => {
  const config = emotionConfig[emotion];
  const sortedWeights = emotionWeights
    ? emotions
        .map((item) => ({ emotion: item, value: emotionWeights[item] ?? 0 }))
        .sort((a, b) => b.value - a.value)
    : null;

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
            Your mood
          </span>
          <div>
            <Typography variant="h4" sx={{ color: config.color }}>
              {config.label}
            </Typography>
            <Typography sx={{ mt: 1, maxWidth: 480, color: 'text.secondary' }}>
              {config.description}
            </Typography>
          </div>
          {sortedWeights ? (
            <div className={styles.weights}>
              {sortedWeights.map(({ emotion: item, value }) => {
                const itemConfig = emotionConfig[item];
                const percent = Math.round(value * 100);

                return (
                  <div key={item} className={styles.weightRow}>
                    <span>{itemConfig.label}</span>
                    <div className={styles.weightBar} aria-label={`${itemConfig.label}: ${percent}%`}>
                      <span style={{ width: `${percent}%`, backgroundColor: itemConfig.accent }} />
                    </div>
                    <strong>{percent}%</strong>
                  </div>
                );
              })}
            </div>
          ) : null}
        </Stack>
      </Card>
    </motion.div>
  );
};
