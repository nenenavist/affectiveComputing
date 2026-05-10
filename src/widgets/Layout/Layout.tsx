import { MusicNoteRounded } from '@mui/icons-material';
import { PropsWithChildren } from 'react';
import { NavLink } from 'react-router-dom';
import styles from './Layout.module.css';

export const Layout = ({ children }: PropsWithChildren) => {
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <NavLink to="/" className={styles.brand} aria-label="На главную Music Mood Matcher">
          <span className={styles.brandMark}>
            <MusicNoteRounded fontSize="small" />
          </span>
          Music Mood Matcher
        </NavLink>
        <nav className={styles.nav} aria-label="Основная навигация">
          <NavLink to="/capture" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}>
            Подбор
          </NavLink>
          <NavLink to="/profile" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}>
            Профиль
          </NavLink>
        </nav>
      </header>
      <main className={styles.content}>{children}</main>
    </div>
  );
};
