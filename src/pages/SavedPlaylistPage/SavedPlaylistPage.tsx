import { DeleteOutlineRounded, OpenInNewRounded } from '@mui/icons-material';
import { Card, CardContent, Snackbar, Stack, Typography } from '@mui/material';
import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { EmotionCard } from '../../entities/emotion/ui/EmotionCard';
import { Track } from '../../entities/playlist/model/types';
import { PlaylistList } from '../../entities/playlist/ui/PlaylistList';
import { formatDate } from '../../shared/lib/formatDate';
import { useMusicMoodStore } from '../../shared/model/musicStore';
import { AppButton } from '../../shared/ui/AppButton/AppButton';
import { EmptyState } from '../../shared/ui/EmptyState/EmptyState';
import { Layout } from '../../widgets/Layout/Layout';
import styles from './SavedPlaylistPage.module.css';

export const SavedPlaylistPage = () => {
  const { playlistId } = useParams();
  const navigate = useNavigate();
  const savedPlaylists = useMusicMoodStore((state) => state.savedPlaylists);
  const likedTracks = useMusicMoodStore((state) => state.likedTracks);
  const deletePlaylist = useMusicMoodStore((state) => state.deletePlaylist);
  const removeTrackFromSavedPlaylist = useMusicMoodStore((state) => state.removeTrackFromSavedPlaylist);
  const toggleLikedTrack = useMusicMoodStore((state) => state.toggleLikedTrack);
  const [snackbar, setSnackbar] = useState('');

  const playlist = savedPlaylists.find((item) => item.id === playlistId);
  const likedTrackIds = useMemo(() => likedTracks.map((track) => track.id), [likedTracks]);

  const handleToggleLike = (track: Track) => {
    const liked = toggleLikedTrack(track);
    setSnackbar(liked ? 'Трек добавлен в любимые.' : 'Трек удалён из любимых.');
  };

  if (!playlist) {
    return (
      <Layout>
        <Stack spacing={3} sx={{ width: 'min(680px, 100%)', mx: 'auto' }}>
          <EmptyState
            title="Плейлист не найден"
            description="Возможно, он был удалён из сохранённых плейлистов."
          />
          <AppButton onClick={() => navigate('/profile')}>Вернуться в профиль</AppButton>
        </Stack>
      </Layout>
    );
  }

  return (
    <Layout>
      <Stack spacing={3}>
        <div>
          <Typography variant="overline" color="primary" sx={{ fontWeight: 900 }}>
            Сохранено {formatDate(playlist.timestamp)}
          </Typography>
          <Typography variant="h2" sx={{ fontSize: { xs: '2.2rem', md: '3.4rem' } }}>
            {playlist.name}
          </Typography>
        </div>
        <div className={styles.grid}>
          <Stack spacing={3}>
            <EmotionCard emotion={playlist.emotion} />
            <Card>
              <CardContent>
                <Stack spacing={2.5}>
                  <Typography variant="h5" sx={{ fontWeight: 850 }}>
                    Предпросмотр Spotify
                  </Typography>
                  <iframe
                    className={styles.embed}
                    title={`${playlist.name} Spotify embed`}
                    src={`https://open.spotify.com/embed/playlist/${playlist.id}`}
                    allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
                    loading="lazy"
                  />
                </Stack>
              </CardContent>
            </Card>
          </Stack>
          <Card>
            <CardContent>
              <Stack spacing={3}>
                <div className={styles.actions}>
                  <AppButton
                    startIcon={<OpenInNewRounded />}
                    onClick={() => window.open(playlist.spotifyUrl, '_blank', 'noopener,noreferrer')}
                  >
                    Открыть в Spotify
                  </AppButton>
                  <AppButton
                    variant="outlined"
                    color="error"
                    startIcon={<DeleteOutlineRounded />}
                    onClick={() => {
                      deletePlaylist(playlist.id);
                      navigate('/profile');
                    }}
                  >
                    Удалить плейлист
                  </AppButton>
                </div>
                <PlaylistList
                  tracks={playlist.tracks}
                  likedTrackIds={likedTrackIds}
                  onToggleLike={handleToggleLike}
                  onRemoveTrack={(trackId) => {
                    removeTrackFromSavedPlaylist(playlist.id, trackId);
                    setSnackbar('Трек удалён из сохранённого плейлиста.');
                  }}
                />
              </Stack>
            </CardContent>
          </Card>
        </div>
      </Stack>
      <Snackbar
        open={Boolean(snackbar)}
        autoHideDuration={2400}
        message={snackbar}
        onClose={() => setSnackbar('')}
      />
    </Layout>
  );
};
