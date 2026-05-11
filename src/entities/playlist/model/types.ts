import { Emotion } from '../../emotion/model/types';

export type Track = {
  id: string;
  title: string;
  artist: string;
  duration: string;
  coverUrl: string;
  spotifyUrl: string;
  musicEmotion?: Emotion;
  musicEmotionScore?: number;
  musicTags?: string[];
};

export type Playlist = {
  id: string;
  name: string;
  emotion: Emotion;
  spotifyUrl: string;
  tracks: Track[];
};

export type SavedPlaylist = Playlist & {
  timestamp: string;
};

export type MoodRequest = {
  text: string;
  hasCameraCapture: boolean;
  image?: string | null;
};
