import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#8f7bea',
      light: '#d8d0ff',
      dark: '#5f4bb6',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#ff9bb3',
      light: '#ffd9e3',
      dark: '#c96a83',
      contrastText: '#422338',
    },
    background: {
      default: '#fff8fb',
      paper: 'rgba(255, 255, 255, 0.82)',
    },
    text: {
      primary: '#242232',
      secondary: '#706b80',
    },
    success: {
      main: '#68c7a2',
    },
    warning: {
      main: '#f5b86a',
    },
    error: {
      main: '#ef7c8e',
    },
  },
  shape: {
    borderRadius: 18,
  },
  typography: {
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    h1: {
      fontWeight: 800,
      letterSpacing: '-0.05em',
    },
    h2: {
      fontWeight: 800,
      letterSpacing: '-0.04em',
    },
    h4: {
      fontWeight: 760,
      letterSpacing: '-0.03em',
    },
    button: {
      fontWeight: 700,
      textTransform: 'none',
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 999,
          boxShadow: 'none',
          paddingInline: 24,
          transition: 'transform 180ms ease, box-shadow 180ms ease, opacity 180ms ease',
          '&:hover': {
            boxShadow: '0 12px 32px rgba(143, 123, 234, 0.24)',
            transform: 'translateY(-1px)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 20,
          boxShadow: '0 20px 60px rgba(68, 52, 107, 0.12)',
          border: '1px solid rgba(255, 255, 255, 0.72)',
          backdropFilter: 'blur(18px)',
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 18,
            backgroundColor: 'rgba(255, 255, 255, 0.78)',
          },
        },
      },
    },
  },
});
