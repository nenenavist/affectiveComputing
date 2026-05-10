import { DeleteOutlineRounded } from '@mui/icons-material';
import { Card, CardContent, Chip, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { emotionConfig } from '../../entities/emotion/model/types';
import { SavedPlaylist } from '../../entities/playlist/model/types';
import { formatDate } from '../../shared/lib/formatDate';
import { EmptyState } from '../../shared/ui/EmptyState/EmptyState';
import styles from './ProfileLibrary.module.css';

type SavedPlaylistsPanelProps = {
  playlists: SavedPlaylist[];
  onDelete: (playlistId: string) => void;
};

export const SavedPlaylistsPanel = ({ playlists, onDelete }: SavedPlaylistsPanelProps) => {
  const navigate = useNavigate();

  return (
    <Card>
      <CardContent>
        <Stack spacing={2.5}>
          <Typography variant="h5" sx={{ fontWeight: 850 }}>
            Сохранённые плейлисты
          </Typography>
          {playlists.length > 0 ? (
            <div className={styles.playlistList}>
              {playlists.map((playlist) => {
                const config = emotionConfig[playlist.emotion];

                return (
                  <article key={playlist.id} className={styles.playlistItem}>
                    <button
                      className={styles.playlistButton}
                      type="button"
                      onClick={() => navigate(`/profile/playlists/${playlist.id}`)}
                    >
                      <div className={styles.playlistName}>{playlist.name}</div>
                      <div className={styles.playlistMeta}>
                        {formatDate(playlist.timestamp)} · {playlist.tracks.length} треков
                      </div>
                      <Chip
                        size="small"
                        label={config.label}
                        sx={{ mt: 1.2, color: config.color, backgroundColor: `${config.accent}26`, fontWeight: 800 }}
                      />
                    </button>
                    <Tooltip title="Удалить плейлист">
                      <IconButton color="error" onClick={() => onDelete(playlist.id)} aria-label="Удалить плейлист">
                        <DeleteOutlineRounded />
                      </IconButton>
                    </Tooltip>
                  </article>
                );
              })}
            </div>
          ) : (
            <EmptyState
              title="Плейлистов пока нет"
              description="Здесь появятся плейлисты, которые вы сохраните после анализа."
            />
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};
