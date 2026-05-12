import {
  DeleteOutlineRounded,
  FavoriteBorderRounded,
  FavoriteRounded,
  PauseRounded,
  PlayArrowRounded,
} from '@mui/icons-material';
import { Chip, CircularProgress, IconButton, Tooltip } from '@mui/material';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Track } from '../../playlist/model/types';
import { searchYoutubeVideo } from '../../../shared/api/backend';
import styles from './TrackCard.module.css';

type TrackCardProps = {
  track: Track;
  liked: boolean;
  onToggleLike: (track: Track) => void;
  onRemove?: (trackId: string) => void;
  activeTrackId?: string | null;
  onActivateTrack?: (trackId: string | null) => void;
};

export const TrackCard = ({
  track,
  liked,
  onToggleLike,
  onRemove,
  activeTrackId,
  onActivateTrack,
}: TrackCardProps) => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [youtubeVideoId, setYoutubeVideoId] = useState<string | null>(null);
  const [youtubeLoading, setYoutubeLoading] = useState(false);
  const [playerLoading, setPlayerLoading] = useState(false);
  const hasPreview = Boolean(track.previewUrl);
  const isActive = activeTrackId === track.id;
  const youtubeQuery = useMemo(() => `${track.artist} - ${track.title}`, [track.artist, track.title]);

  useEffect(() => {
    let cancelled = false;

    if (hasPreview) {
      setYoutubeVideoId(null);
      setYoutubeLoading(false);
      return () => {
        cancelled = true;
      };
    }

    setYoutubeLoading(true);
    void searchYoutubeVideo(youtubeQuery)
      .then((videoId) => {
        if (!cancelled) {
          setYoutubeVideoId(videoId);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setYoutubeLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [hasPreview, youtubeQuery]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }

    if (isActive && hasPreview) {
      setPlayerLoading(true);
      void audio.play().catch(() => setPlayerLoading(false));
      return;
    }

    audio.pause();
    audio.currentTime = 0;
  }, [hasPreview, isActive]);

  const togglePlayback = () => {
    if (!onActivateTrack) {
      return;
    }

    if (isActive) {
      onActivateTrack(null);
      return;
    }

    if (!hasPreview && !youtubeVideoId) {
      return;
    }

    onActivateTrack(track.id);
  };

  const playbackLabel = hasPreview ? 'Аудио preview' : 'YouTube fallback';
  const canPlay = hasPreview || Boolean(youtubeVideoId);
  const isLoading = playerLoading || youtubeLoading;

  return (
    <article className={styles.card}>
      <img className={styles.cover} src={track.coverUrl} alt={`Обложка трека ${track.title}`} loading="lazy" />
      <div className={styles.trackInfo}>
        <div className={styles.title}>{track.title}</div>
        <div className={styles.meta}>
          <span className={styles.artist}>{track.artist}</span>
          <span aria-hidden="true">•</span>
          <span>{track.duration}</span>
          <span aria-hidden="true">•</span>
          <span>{playbackLabel}</span>
        </div>
        {track.musicEmotion ? (
          <div className={styles.musicMeta}>
            <Chip
              size="small"
              label={`${track.musicEmotion} ${track.musicEmotionScore ? Math.round(track.musicEmotionScore * 100) : ''}%`}
            />
          </div>
        ) : null}
      </div>
      <div className={styles.actions}>
        <Tooltip title={isActive ? 'Пауза' : canPlay ? 'Играть на сайте' : 'Трек временно недоступен'}>
          <span>
            <IconButton
              color={isActive ? 'primary' : 'default'}
              onClick={togglePlayback}
              disabled={!canPlay || isLoading}
              aria-label={isActive ? 'Поставить на паузу' : 'Играть трек'}
            >
              {isLoading ? <CircularProgress size={22} /> : isActive ? <PauseRounded /> : <PlayArrowRounded />}
            </IconButton>
          </span>
        </Tooltip>
        <Tooltip title={liked ? 'Убрать из любимых' : 'Добавить в любимые'}>
          <IconButton color={liked ? 'secondary' : 'default'} onClick={() => onToggleLike(track)} aria-label={liked ? 'Убрать из любимых' : 'Добавить в любимые'}>
            {liked ? <FavoriteRounded /> : <FavoriteBorderRounded />}
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
      {hasPreview && isActive ? (
        <div className={styles.playerRow}>
          <audio
            ref={audioRef}
            className={styles.audioPlayer}
            src={track.previewUrl ?? undefined}
            controls
            autoPlay
            onCanPlay={() => setPlayerLoading(false)}
            onWaiting={() => setPlayerLoading(true)}
            onPlay={() => setPlayerLoading(false)}
            onPause={() => onActivateTrack?.(null)}
            onEnded={() => onActivateTrack?.(null)}
          />
        </div>
      ) : null}
      {!hasPreview && isActive && youtubeVideoId ? (
        <div className={styles.playerRow}>
          <iframe
            className={styles.youtubePlayer}
            title={`${track.artist} - ${track.title}`}
            src={`https://www.youtube.com/embed/${youtubeVideoId}?autoplay=1&rel=0`}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          />
        </div>
      ) : null}
    </article>
  );
};
