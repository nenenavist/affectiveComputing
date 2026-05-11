import { SavedPlaylist, Track } from '../../entities/playlist/model/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export type User = {
  id: number;
  email: string;
};

export type ProfileSnapshot = {
  savedPlaylists: SavedPlaylist[];
  likedTracks: Track[];
};

export type AuthResponse = {
  token: string;
  user: User;
  profile: ProfileSnapshot;
};

type ApiError = {
  detail?: string;
};

const readError = async (response: Response, fallback: string) => {
  try {
    const error = (await response.json()) as ApiError;
    return error.detail || fallback;
  } catch {
    return fallback;
  }
};

export const requestAuth = async (
  mode: 'login' | 'register',
  email: string,
  password: string,
): Promise<AuthResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/auth/${mode}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new Error(await readError(response, 'Не удалось выполнить вход.'));
  }

  return response.json() as Promise<AuthResponse>;
};

export const syncProfile = async (token: string, profile: ProfileSnapshot): Promise<ProfileSnapshot> => {
  const response = await fetch(`${API_BASE_URL}/api/profile`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(profile),
  });

  if (!response.ok) {
    throw new Error(await readError(response, 'Не удалось синхронизировать профиль.'));
  }

  return response.json() as Promise<ProfileSnapshot>;
};
