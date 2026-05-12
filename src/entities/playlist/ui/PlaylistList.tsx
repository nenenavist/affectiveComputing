import { Stack, Typography } from '@mui/material';
import { useEffect, useMemo, useState } from 'react';
import { TrackCard } from '../../track/ui/TrackCard';
import { Track } from '../model/types';
import { AppButton } from '../../../shared/ui/AppButton/AppButton';
import styles from './PlaylistList.module.css';

type PlaylistListProps = {
  tracks: Track[];
  likedTrackIds: string[];
  onToggleLike: (track: Track) => void;
  onRemoveTrack?: (trackId: string) => void;
  title?: string;
};

export const PlaylistList = ({
  tracks,
  likedTrackIds,
  onToggleLike,
  onRemoveTrack,
  title = 'Рекомендованные треки',
}: PlaylistListProps) => {
  const [visibleCount, setVisibleCount] = useState(5);
  const [activeTrackId, setActiveTrackId] = useState<string | null>(null);
  const visibleTracks = useMemo(() => tracks.slice(0, visibleCount), [tracks, visibleCount]);
  const hasMore = visibleCount < tracks.length;

  useEffect(() => {
    setVisibleCount(5);
    setActiveTrackId(null);
  }, [tracks]);

  return (
    <Stack spacing={2}>
      <div className={styles.header}>
        <Typography variant="h5" sx={{ fontWeight: 850 }}>
          {title}
        </Typography>
        <span className={styles.count}>
          Показано {visibleTracks.length} из {tracks.length}
        </span>
      </div>
      <div className={styles.list}>
        {visibleTracks.map((track) => (
          <TrackCard
            key={track.id}
            track={track}
            liked={likedTrackIds.includes(track.id)}
            onToggleLike={onToggleLike}
            onRemove={
              onRemoveTrack
                ? (trackId) => {
                    if (activeTrackId === trackId) {
                      setActiveTrackId(null);
                    }
                    onRemoveTrack(trackId);
                  }
                : undefined
            }
            activeTrackId={activeTrackId}
            onActivateTrack={setActiveTrackId}
          />
        ))}
      </div>
      {hasMore ? (
        <div className={styles.showMore}>
          <AppButton variant="outlined" onClick={() => setVisibleCount((count) => Math.min(count + 5, tracks.length))}>
            Показать ещё 5
          </AppButton>
        </div>
      ) : null}
    </Stack>
  );
};
