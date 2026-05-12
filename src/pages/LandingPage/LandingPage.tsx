import { AutoAwesomeRounded, MusicNoteRounded } from '@mui/icons-material';
import { Typography } from '@mui/material';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { AppButton } from '../../shared/ui/AppButton/AppButton';
import styles from './LandingPage.module.css';

const highlights = [
  {
    title: 'Подбор по настроению',
    text: 'Используйте камеру, текстовое описание или оба варианта, чтобы точнее подобрать плейлист.',
  },
  {
    title: 'Музыка внутри сайта',
    text: 'Слушайте Spotify preview прямо в приложении, а треки без preview открываются через YouTube fallback.',
  },
  {
    title: 'Личная библиотека',
    text: 'Сохраняйте плейлисты и любимые треки локально, чтобы быстро вернуться к ним.',
  },
];

export const LandingPage = () => {
  const navigate = useNavigate();

  return (
    <section className={styles.page}>
      <motion.div
        className={styles.hero}
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: 'easeOut' }}
      >
        <span className={styles.badge}>
          <AutoAwesomeRounded fontSize="small" />
          Генератор плейлистов по эмоциям
        </span>
        <Typography variant="h1" sx={{ fontSize: { xs: '3rem', md: '5.5rem' } }}>
          Music Mood Matcher
        </Typography>
        <p className={styles.subtitle}>Сгенерируйте плейлист на основе ваших эмоций</p>
        <div className={styles.actions}>
          <AppButton startIcon={<MusicNoteRounded />} onClick={() => navigate('/permissions')}>
            Начать
          </AppButton>
          <AppButton variant="outlined" onClick={() => navigate('/profile')}>
            Открыть профиль
          </AppButton>
        </div>
        <div className={styles.preview}>
          {highlights.map((highlight) => (
            <article key={highlight.title} className={styles.previewCard}>
              <div className={styles.previewTitle}>{highlight.title}</div>
              <div className={styles.previewText}>{highlight.text}</div>
            </article>
          ))}
        </div>
      </motion.div>
    </section>
  );
};
