import { Emotion } from '../../emotion/model/types';
import { MoodRequest, Playlist, Track } from '../model/types';

const covers = [
  'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=320&q=80',
  'https://images.unsplash.com/photo-1516280440614-37939bbacd81?auto=format&fit=crop&w=320&q=80',
  'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=320&q=80',
  'https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=320&q=80',
  'https://images.unsplash.com/photo-1494232410401-ad00d5433cfa?auto=format&fit=crop&w=320&q=80',
  'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=320&q=80',
];

const tracksByEmotion: Record<Emotion, Omit<Track, 'coverUrl' | 'spotifyUrl'>[]> = {
  happy: [
    { id: 'happy-1', title: 'Солнечные шаги', artist: 'Luna Vale', duration: '3:18' },
    { id: 'happy-2', title: 'Персиковое небо', artist: 'North Arcade', duration: '2:54' },
    { id: 'happy-3', title: 'Утренний свет', artist: 'The Paper Planes', duration: '3:41' },
    { id: 'happy-4', title: 'Лёгкое сияние', artist: 'Mira Coast', duration: '3:07' },
    { id: 'happy-5', title: 'Цветная пятница', artist: 'Echo Honey', duration: '2:48' },
  ],
  sad: [
    { id: 'sad-1', title: 'Дождь по стеклу', artist: 'Elliot Lane', duration: '3:56' },
    { id: 'sad-2', title: 'Тихая гавань', artist: 'June Atlas', duration: '4:12' },
    { id: 'sad-3', title: 'Письма из синей комнаты', artist: 'Orchid Field', duration: '3:33' },
    { id: 'sad-4', title: 'Последний поезд домой', artist: 'Soft Mercury', duration: '4:04' },
    { id: 'sad-5', title: 'Отлив', artist: 'Anya Reed', duration: '3:47' },
  ],
  angry: [
    { id: 'angry-1', title: 'Пульс на пределе', artist: 'Metro Static', duration: '2:59' },
    { id: 'angry-2', title: 'Бетонное сердце', artist: 'Violet Fuse', duration: '3:28' },
    { id: 'angry-3', title: 'Нет сигнала', artist: 'Rook District', duration: '3:36' },
    { id: 'angry-4', title: 'После вспышки', artist: 'Glass Sirens', duration: '3:11' },
    { id: 'angry-5', title: 'Острые края', artist: 'Nova Riot', duration: '2:51' },
  ],
  neutral: [
    { id: 'neutral-1', title: 'Чистый лист', artist: 'Aster Mode', duration: '3:24' },
    { id: 'neutral-2', title: 'Мягкий фокус', artist: 'Calm Index', duration: '3:32' },
    { id: 'neutral-3', title: 'Место у окна', artist: 'Haven North', duration: '3:46' },
    { id: 'neutral-4', title: 'Ровный свет', artist: 'Nora Finch', duration: '3:05' },
    { id: 'neutral-5', title: 'Маленькие ритуалы', artist: 'The Local Forecast', duration: '2:58' },
  ],
};

const emotionKeywords: Record<Emotion, string[]> = {
  happy: ['happy', 'great', 'good', 'excited', 'joy', 'love', 'amazing', 'calm', 'рад', 'счаст', 'хорош', 'люблю', 'восторг'],
  sad: ['sad', 'tired', 'lonely', 'hurt', 'cry', 'bad', 'down', 'empty', 'груст', 'устал', 'одинок', 'плохо', 'плак'],
  angry: ['angry', 'mad', 'furious', 'stress', 'annoyed', 'hate', 'rage', 'зл', 'бесит', 'стресс', 'ненавиж', 'ярость'],
  neutral: ['okay', 'fine', 'normal', 'neutral', 'usual', 'average', 'норм', 'обычно', 'нейтраль', 'ровно'],
};

const playlistNames: Record<Emotion, string> = {
  happy: 'Пастельный утренний заряд',
  sad: 'Мягкий дождливый вечер',
  angry: 'Выпустить напряжение',
  neutral: 'Ровный дневной ритм',
};

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

const detectEmotion = ({ text, hasCameraCapture }: MoodRequest): Emotion => {
  const normalizedText = text.toLowerCase();
  const matchedEmotion = (Object.keys(emotionKeywords) as Emotion[]).find((emotion) =>
    emotionKeywords[emotion].some((keyword) => normalizedText.includes(keyword)),
  );

  if (matchedEmotion) {
    return matchedEmotion;
  }

  if (hasCameraCapture) {
    return 'happy';
  }

  return 'neutral';
};

const buildTracks = (emotion: Emotion): Track[] => {
  return tracksByEmotion[emotion].map((track, index) => ({
    ...track,
    coverUrl: covers[index % covers.length],
    spotifyUrl: `https://open.spotify.com/track/${track.id}`,
  }));
};

export const generateMoodPlaylist = async (request: MoodRequest): Promise<Playlist> => {
  await wait(1600);

  if (request.text.toLowerCase().includes('api error')) {
    throw new Error('Анализ настроения временно недоступен. Попробуйте ещё раз.');
  }

  const emotion = detectEmotion(request);
  const playlistId = `mmm-${emotion}-playlist`;

  return {
    id: playlistId,
    name: playlistNames[emotion],
    emotion,
    spotifyUrl: `https://open.spotify.com/playlist/${playlistId}`,
    tracks: buildTracks(emotion),
  };
};
