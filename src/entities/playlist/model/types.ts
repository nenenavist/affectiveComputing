import { Emotion } from '../../emotion/model/types';

export type Track = {
  id: string;
  title: string;
  artist: string;
  duration: string;
  coverUrl: string;
  spotifyUrl: string;
  previewUrl?: string | null;
  source?: string;
  musicEmotion?: Emotion;
  musicEmotionScore?: number;
  musicTags?: string[];
};

export type EmotionWeights = Record<Emotion, number>;

export type Playlist = {
  id: string;
  playlistId?: string;
  name: string;
  emotion: Emotion;
  emotionWeights?: EmotionWeights;
  spotifyUrl: string;
  tracks: Track[];
  audioTargets?: Record<string, number>;
  seedGenres?: string[];
};

export type SavedPlaylist = Playlist & {
  timestamp: string;
};

export type MoodRequest = {
  text: string;
  hasCameraCapture: boolean;
  image?: string | null;
};
