import { Card, CardContent, Snackbar, Stack, TextField, Typography } from '@mui/material';
import { useState } from 'react';
import { Track } from '../../entities/playlist/model/types';
import { useMusicMoodStore } from '../../shared/model/musicStore';
import { AppButton } from '../../shared/ui/AppButton/AppButton';
import { Layout } from '../../widgets/Layout/Layout';
import { ProfileLibrary } from '../../widgets/ProfileLibrary/ProfileLibrary';

export const ProfilePage = () => {
  const savedPlaylists = useMusicMoodStore((state) => state.savedPlaylists);
  const likedTracks = useMusicMoodStore((state) => state.likedTracks);
  const user = useMusicMoodStore((state) => state.user);
  const login = useMusicMoodStore((state) => state.login);
  const register = useMusicMoodStore((state) => state.register);
  const logout = useMusicMoodStore((state) => state.logout);
  const syncProfileToBackend = useMusicMoodStore((state) => state.syncProfileToBackend);
  const deletePlaylist = useMusicMoodStore((state) => state.deletePlaylist);
  const toggleLikedTrack = useMusicMoodStore((state) => state.toggleLikedTrack);
  const [snackbar, setSnackbar] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleDeletePlaylist = (playlistId: string) => {
    deletePlaylist(playlistId);
    setSnackbar('Плейлист удалён.');
  };

  const handleRemoveLikedTrack = (track: Track) => {
    toggleLikedTrack(track);
    setSnackbar('Трек удалён из любимых.');
  };

  const handleAuth = async (mode: 'login' | 'register') => {
    setIsSubmitting(true);

    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register(email, password);
      }
      setPassword('');
      setSnackbar(mode === 'login' ? 'Вход выполнен.' : 'Аккаунт создан.');
    } catch (error) {
      setSnackbar(error instanceof Error ? error.message : 'Ошибка авторизации.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSync = async () => {
    setIsSubmitting(true);

    try {
      await syncProfileToBackend();
      setSnackbar('Профиль синхронизирован.');
    } catch (error) {
      setSnackbar(error instanceof Error ? error.message : 'Ошибка синхронизации.');
    } finally {
      setIsSubmitting(false);
    }
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
            Сохранённые плейлисты и любимые треки можно хранить локально или синхронизировать с backend.
          </Typography>
        </div>
        <Card>
          <CardContent>
            {user ? (
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ alignItems: { sm: 'center' } }}>
                <Typography sx={{ flex: 1 }}>Вы вошли как {user.email}</Typography>
                <AppButton disabled={isSubmitting} onClick={() => void handleSync()}>
                  Синхронизировать
                </AppButton>
                <AppButton variant="outlined" onClick={logout}>
                  Выйти
                </AppButton>
              </Stack>
            ) : (
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
                <TextField
                  label="Email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
                <TextField
                  label="Пароль"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <AppButton disabled={isSubmitting} onClick={() => void handleAuth('login')}>
                  Войти
                </AppButton>
                <AppButton variant="outlined" disabled={isSubmitting} onClick={() => void handleAuth('register')}>
                  Создать
                </AppButton>
              </Stack>
            )}
          </CardContent>
        </Card>
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
