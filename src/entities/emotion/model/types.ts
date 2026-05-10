export type Emotion = 'happy' | 'sad' | 'angry' | 'neutral';

export type EmotionConfig = {
  label: string;
  description: string;
  color: string;
  background: string;
  accent: string;
};

export const emotionConfig: Record<Emotion, EmotionConfig> = {
  happy: {
    label: 'Радость',
    description: 'Обнаружено светлое, тёплое и энергичное настроение.',
    color: '#3c8f72',
    background: 'linear-gradient(135deg, #e2fff2 0%, #fff8cc 100%)',
    accent: '#68c7a2',
  },
  sad: {
    label: 'Грусть',
    description: 'Мягкие и задумчивые треки для спокойного момента.',
    color: '#5275b8',
    background: 'linear-gradient(135deg, #e9f0ff 0%, #f6edff 100%)',
    accent: '#84a8ff',
  },
  angry: {
    label: 'Злость',
    description: 'Собранные и интенсивные треки, чтобы выпустить напряжение.',
    color: '#bc5965',
    background: 'linear-gradient(135deg, #ffe5e9 0%, #fff0dc 100%)',
    accent: '#ef7c8e',
  },
  neutral: {
    label: 'Нейтрально',
    description: 'Сбалансированное звучание для ровного и спокойного состояния.',
    color: '#746985',
    background: 'linear-gradient(135deg, #f7f3ff 0%, #eefaf6 100%)',
    accent: '#b9a8f6',
  },
};
