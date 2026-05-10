import { Snackbar, Stack, Typography } from '@mui/material';
import { useState } from 'react';
import { Track } from '../../entities/playlist/model/types';
import { useMusicMoodStore } from '../../shared/model/musicStore';
import { Layout } from '../../widgets/Layout/Layout';
import { ProfileLibrary } from '../../widgets/ProfileLibrary/ProfileLibrary';

export const ProfilePage = () => {
  const savedPlaylists = useMusicMoodStore((state) => state.savedPlaylists);
  const likedTracks = useMusicMoodStore((state) => state.likedTracks);
  const deletePlaylist = useMusicMoodStore((state) => state.deletePlaylist);
  const toggleLikedTrack = useMusicMoodStore((state) => state.toggleLikedTrack);
  const [snackbar, setSnackbar] = useState('');

  const handleDeletePlaylist = (playlistId: string) => {
    deletePlaylist(playlistId);
    setSnackbar('Плейлист удалён.');
  };

  const handleRemoveLikedTrack = (track: Track) => {
    toggleLikedTrack(track);
    setSnackbar('Трек удалён из любимых.');
  };

  return (
    <Layout>
      <Stack spacing={3}>
        <div>
          <Typography variant="overline" color="primary" sx={{ fontWeight: 900 }}>
            Профиль
          </Typography>
          <Typography variant="h2" sx={{ fontSize: { xs: '2.2rem', md: '3.4rem' } }}>
            Ваша музыкальная библиотека
          </Typography>
          <Typography sx={{ mt: 1, maxWidth: 650, color: 'text.secondary' }}>
            Сохранённые плейлисты и любимые треки хранятся локально на этом устройстве.
          </Typography>
        </div>
        <ProfileLibrary
          playlists={savedPlaylists}
          likedTracks={likedTracks}
          onDeletePlaylist={handleDeletePlaylist}
          onRemoveLikedTrack={handleRemoveLikedTrack}
        />
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
