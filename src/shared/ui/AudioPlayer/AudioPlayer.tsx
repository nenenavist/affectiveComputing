import { useRef, useState, useEffect } from 'react';
import { PlayArrowRounded, PauseRounded } from '@mui/icons-material';
import { IconButton } from '@mui/material';
import styles from './AudioPlayer.module.css';

type AudioPlayerProps = {
  audioUrl: string;
  title: string;
  artist: string;
};

export const AudioPlayer = ({ audioUrl, title, artist }: AudioPlayerProps) => {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const togglePlay = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleEnded = () => {
    setIsPlaying(false);
  };

  useEffect(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.addEventListener('ended', handleEnded);
      return () => {
        audio.removeEventListener('ended', handleEnded);
      };
    }
  }, []);

  if (!audioUrl) {
    return null;
  }

  return (
    <div className={styles.player}>
      <audio ref={audioRef} src={audioUrl} />
      <IconButton onClick={togglePlay} aria-label={isPlaying ? 'Пауза' : 'Воспроизвести'}>
        {isPlaying ? <PauseRounded /> : <PlayArrowRounded />}
      </IconButton>
      <div className={styles.trackInfo}>
        <div className={styles.title}>{title}</div>
        <div className={styles.artist}>{artist}</div>
      </div>
    </div>
  );
};
