import { DeleteOutlineRounded, FavoriteBorderRounded, FavoriteRounded, OpenInNewRounded } from '@mui/icons-material';
import { Chip, IconButton, Tooltip } from '@mui/material';
import { Track } from '../../playlist/model/types';
import styles from './TrackCard.module.css';

type TrackCardProps = {
  track: Track;
  liked: boolean;
  onToggleLike: (track: Track) => void;
  onRemove?: (trackId: string) => void;
};

export const TrackCard = ({ track, liked, onToggleLike, onRemove }: TrackCardProps) => {
  const openTrack = () => {
    window.open(track.spotifyUrl, '_blank', 'noopener,noreferrer');
  };

  return (
    <article className={styles.card}>
      <img className={styles.cover} src={track.coverUrl} alt={`Обложка трека ${track.title}`} loading="lazy" />
      <button className={styles.trackButton} type="button" onClick={openTrack}>
        <div className={styles.title}>{track.title}</div>
        <div className={styles.meta}>
          <span className={styles.artist}>{track.artist}</span>
          <span aria-hidden="true">•</span>
          <span>{track.duration}</span>
        </div>
        {track.musicEmotion ? (
          <div className={styles.musicMeta}>
            <Chip
              size="small"
              label={`${track.musicEmotion} ${track.musicEmotionScore ? Math.round(track.musicEmotionScore * 100) : ''}%`}
            />
          </div>
        ) : null}
      </button>
      <div className={styles.actions}>
        <Tooltip title={liked ? 'Убрать из любимых' : 'Добавить в любимые'}>
          <IconButton color={liked ? 'secondary' : 'default'} onClick={() => onToggleLike(track)} aria-label={liked ? 'Убрать из любимых' : 'Добавить в любимые'}>
            {liked ? <FavoriteRounded /> : <FavoriteBorderRounded />}
          </IconButton>
        </Tooltip>
        <Tooltip title="Открыть в Spotify">
          <IconButton onClick={openTrack} aria-label="Открыть трек в Spotify">
            <OpenInNewRounded />
          </IconButton>
        </Tooltip>
        {onRemove ? (
          <Tooltip title="Убрать из плейлиста">
            <IconButton color="error" onClick={() => onRemove(track.id)} aria-label="Убрать трек">
              <DeleteOutlineRounded />
            </IconButton>
          </Tooltip>
        ) : null}
      </div>
    </article>
  );
};
