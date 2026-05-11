import { MoodRequest, Playlist } from '../model/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

type ApiErrorResponse = {
  detail?: string;
};

export const generateMoodPlaylist = async (request: MoodRequest): Promise<Playlist> => {
  const response = await fetch(`${API_BASE_URL}/api/mood/playlist`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    let message = 'Анализ настроения временно недоступен. Попробуйте ещё раз.';

    try {
      const error = (await response.json()) as ApiErrorResponse;
      message = error.detail || message;
    } catch {
      // Keep the default message when the backend returns a non-JSON error.
    }

    throw new Error(message);
  }

  return response.json() as Promise<Playlist>;
};
