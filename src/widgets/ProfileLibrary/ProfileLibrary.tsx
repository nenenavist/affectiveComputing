import { SavedPlaylist, Track } from '../../entities/playlist/model/types';
import { LikedTracksPanel } from './LikedTracksPanel';
import { SavedPlaylistsPanel } from './SavedPlaylistsPanel';
import styles from './ProfileLibrary.module.css';

type ProfileLibraryProps = {
  playlists: SavedPlaylist[];
  likedTracks: Track[];
  onDeletePlaylist: (playlistId: string) => void;
  onRemoveLikedTrack: (track: Track) => void;
};

export const ProfileLibrary = ({
  playlists,
  likedTracks,
  onDeletePlaylist,
  onRemoveLikedTrack,
}: ProfileLibraryProps) => {
  return (
    <div className={styles.grid}>
      <SavedPlaylistsPanel playlists={playlists} onDelete={onDeletePlaylist} />
      <LikedTracksPanel tracks={likedTracks} onRemove={onRemoveLikedTrack} />
    </div>
  );
};
