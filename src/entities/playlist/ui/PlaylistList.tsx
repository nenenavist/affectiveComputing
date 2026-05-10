import { Stack, Typography } from '@mui/material';
import { TrackCard } from '../../track/ui/TrackCard';
import { Track } from '../model/types';
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
  return (
    <Stack spacing={2}>
      <div className={styles.header}>
        <Typography variant="h5" sx={{ fontWeight: 850 }}>
          {title}
        </Typography>
        <span className={styles.count}>{tracks.length} треков</span>
      </div>
      <div className={styles.list}>
        {tracks.map((track) => (
          <TrackCard
            key={track.id}
            track={track}
            liked={likedTrackIds.includes(track.id)}
            onToggleLike={onToggleLike}
            onRemove={onRemoveTrack}
          />
        ))}
      </div>
    </Stack>
  );
};
