import { Card, CardContent, Stack, Typography } from '@mui/material';
import { Track } from '../../entities/playlist/model/types';
import { TrackCard } from '../../entities/track/ui/TrackCard';
import { EmptyState } from '../../shared/ui/EmptyState/EmptyState';

type LikedTracksPanelProps = {
  tracks: Track[];
  onRemove: (track: Track) => void;
};

export const LikedTracksPanel = ({ tracks, onRemove }: LikedTracksPanelProps) => {
  return (
    <Card>
      <CardContent>
        <Stack spacing={2.5}>
          <Typography variant="h5" sx={{ fontWeight: 850 }}>
            Любимые треки
          </Typography>
          {tracks.length > 0 ? (
            <Stack spacing={1.5}>
              {tracks.map((track) => (
                <TrackCard key={track.id} track={track} liked onToggleLike={onRemove} />
              ))}
            </Stack>
          ) : (
            <EmptyState title="Любимых треков пока нет" description="Нажмите на сердечко у любого трека, чтобы сохранить его здесь." />
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};
