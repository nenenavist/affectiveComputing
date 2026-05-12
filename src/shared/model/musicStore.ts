import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Playlist, SavedPlaylist, Track } from '../../entities/playlist/model/types';
import { requestAuth, syncProfile, User } from '../api/backend';

type MoodPreferences = {
  cameraEnabled: boolean;
  consentToProcessing: boolean;
};

type MoodInput = {
  text: string;
  hasCameraCapture: boolean;
  image?: string | null;
};

type MusicMoodState = {
  authToken: string | null;
  user: User | null;
  preferences: MoodPreferences;
  moodInput: MoodInput;
  currentPlaylist: Playlist | null;
  savedPlaylists: SavedPlaylist[];
  likedTracks: Track[];
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  syncProfileToBackend: () => Promise<void>;
  setPreferences: (preferences: MoodPreferences) => void;
  setMoodInput: (input: MoodInput) => void;
  setCurrentPlaylist: (playlist: Playlist) => void;
  removeTrackFromCurrentPlaylist: (trackId: string) => void;
  saveCurrentPlaylist: () => boolean;
  deletePlaylist: (playlistId: string) => void;
  removeTrackFromSavedPlaylist: (playlistId: string, trackId: string) => void;
  toggleLikedTrack: (track: Track) => boolean;
  removeLikedTrack: (trackId: string) => void;
  isTrackLiked: (trackId: string) => boolean;
};

const defaultPreferences: MoodPreferences = {
  cameraEnabled: false,
  consentToProcessing: false,
};

export const useMusicMoodStore = create<MusicMoodState>()(
  persist(
    (set, get) => ({
      authToken: null,
      user: null,
      preferences: defaultPreferences,
      moodInput: {
        text: '',
        hasCameraCapture: false,
      },
      currentPlaylist: null,
      savedPlaylists: [],
      likedTracks: [],
      login: async (email, password) => {
        const response = await requestAuth('login', email, password);
        set({
          authToken: response.token,
          user: response.user,
          savedPlaylists: response.profile.savedPlaylists,
          likedTracks: response.profile.likedTracks,
        });
      },
      register: async (email, password) => {
        const response = await requestAuth('register', email, password);
        set({
          authToken: response.token,
          user: response.user,
          savedPlaylists: response.profile.savedPlaylists,
          likedTracks: response.profile.likedTracks,
        });
      },
      logout: () => set({ authToken: null, user: null }),
      syncProfileToBackend: async () => {
        const { authToken, savedPlaylists, likedTracks } = get();

        if (!authToken) {
          return;
        }

        const profile = await syncProfile(authToken, { savedPlaylists, likedTracks });
        set({
          savedPlaylists: profile.savedPlaylists,
          likedTracks: profile.likedTracks,
        });
      },
      setPreferences: (preferences) => set({ preferences }),
      setMoodInput: (input) => set({ moodInput: input }),
      setCurrentPlaylist: (playlist) => set({ currentPlaylist: playlist }),
      removeTrackFromCurrentPlaylist: (trackId) =>
        set((state) => ({
          currentPlaylist: state.currentPlaylist
            ? {
                ...state.currentPlaylist,
                tracks: state.currentPlaylist.tracks.filter((track) => track.id !== trackId),
              }
            : null,
        })),
      saveCurrentPlaylist: () => {
        const playlist = get().currentPlaylist;

        if (!playlist) {
          return false;
        }

        const alreadySaved = get().savedPlaylists.some((item) => item.id === playlist.id);

        if (alreadySaved) {
          return false;
        }

        set((state) => ({
          savedPlaylists: [
            {
              ...playlist,
              timestamp: new Date().toISOString(),
            },
            ...state.savedPlaylists,
          ],
        }));

        return true;
      },
      deletePlaylist: (playlistId) =>
        set((state) => ({
          savedPlaylists: state.savedPlaylists.filter((playlist) => playlist.id !== playlistId),
        })),
      removeTrackFromSavedPlaylist: (playlistId, trackId) =>
        set((state) => ({
          savedPlaylists: state.savedPlaylists.map((playlist) =>
            playlist.id === playlistId
              ? {
                  ...playlist,
                  tracks: playlist.tracks.filter((track) => track.id !== trackId),
                }
              : playlist,
          ),
        })),
      toggleLikedTrack: (track) => {
        const isLiked = get().likedTracks.some((item) => item.id === track.id);

        set((state) => ({
          likedTracks: isLiked
            ? state.likedTracks.filter((item) => item.id !== track.id)
            : [track, ...state.likedTracks],
        }));

        return !isLiked;
      },
      removeLikedTrack: (trackId) =>
        set((state) => ({
          likedTracks: state.likedTracks.filter((track) => track.id !== trackId),
        })),
      isTrackLiked: (trackId) => get().likedTracks.some((track) => track.id === trackId),
    }),
    {
      name: 'music-mood-matcher',
      partialize: (state) => ({
        preferences: state.preferences,
        authToken: state.authToken,
        user: state.user,
        currentPlaylist: state.currentPlaylist,
        savedPlaylists: state.savedPlaylists,
        likedTracks: state.likedTracks,
      }),
    },
  ),
);
