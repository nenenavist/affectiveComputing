import { useEffect, useRef, useState } from 'react';

type YouTubePlayerProps = {
  videoId: string;
  title: string;
};

declare global {
  interface Window {
    YT: any;
    onYouTubeIframeAPIReady: () => void;
  }
}

export const YouTubePlayer = ({ videoId, title }: YouTubePlayerProps) => {
  const playerRef = useRef<any>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    // Load YouTube IFrame API
    if (!window.YT) {
      const tag = document.createElement('script');
      tag.src = 'https://www.youtube.com/iframe_api';
      const firstScriptTag = document.getElementsByTagName('script')[0];
      firstScriptTag.parentNode?.insertBefore(tag, firstScriptTag);

      window.onYouTubeIframeAPIReady = () => {
        setIsReady(true);
      };
    } else {
      setIsReady(true);
    }
  }, []);

  useEffect(() => {
    if (isReady && videoId && !playerRef.current) {
      playerRef.current = new window.YT.Player(`youtube-player-${videoId}`, {
        height: '60',
        width: '100%',
        videoId: videoId,
        playerVars: {
          playsinline: 1,
          controls: 1,
          modestbranding: 1,
          rel: 0,
        },
      });
    }

    return () => {
      if (playerRef.current) {
        playerRef.current.destroy();
        playerRef.current = null;
      }
    };
  }, [isReady, videoId]);

  if (!videoId) {
    return null;
  }

  return (
    <div style={{ width: '100%', marginTop: '8px' }}>
      <div id={`youtube-player-${videoId}`} />
    </div>
  );
};
