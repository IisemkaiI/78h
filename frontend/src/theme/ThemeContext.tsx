import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export type Theme = 'light' | 'dark';

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const STORAGE_KEY = 'education-platform-theme';
const ThemeContext = createContext<ThemeContextValue | null>(null);

function isTheme(value: string | null): value is Theme {
  return value === 'light' || value === 'dark';
}

function initialTheme(): Theme {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (isTheme(stored)) {
      return stored;
    }
  } catch {
    // The system preference remains available when browser storage is disabled.
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute(
      'content',
      theme === 'dark' ? '#151a17' : '#f5f4ee',
    );
    document.querySelector('meta[name="color-scheme"]')?.setAttribute('content', theme);
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Theme switching still works for the current page when storage is disabled.
    }
  }, [theme]);

  useEffect(() => {
    const handleStorage = (event: StorageEvent): void => {
      if (event.key === STORAGE_KEY && isTheme(event.newValue)) {
        setTheme(event.newValue);
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'));
  }, []);

  const value = useMemo(() => ({ theme, toggleTheme }), [theme, toggleTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (context === null) {
    throw new Error('useTheme must be used inside ThemeProvider.');
  }
  return context;
}
