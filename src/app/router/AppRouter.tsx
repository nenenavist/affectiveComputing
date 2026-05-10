import { Navigate, Route, Routes } from 'react-router-dom';
import { CapturePage } from '../../pages/CapturePage/CapturePage';
import { LandingPage } from '../../pages/LandingPage/LandingPage';
import { LoadingPage } from '../../pages/LoadingPage/LoadingPage';
import { PermissionsPage } from '../../pages/PermissionsPage/PermissionsPage';
import { ProfilePage } from '../../pages/ProfilePage/ProfilePage';
import { ResultPage } from '../../pages/ResultPage/ResultPage';
import { SavedPlaylistPage } from '../../pages/SavedPlaylistPage/SavedPlaylistPage';

export const AppRouter = () => {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/permissions" element={<PermissionsPage />} />
      <Route path="/capture" element={<CapturePage />} />
      <Route path="/loading" element={<LoadingPage />} />
      <Route path="/result" element={<ResultPage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/profile/playlists/:playlistId" element={<SavedPlaylistPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};
