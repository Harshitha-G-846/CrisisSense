import React, { createContext, useContext, useEffect, useState } from 'react'

export type ThemeMode = 'light' | 'dark' | 'system'

interface ThemeContextType {
  theme: ThemeMode
  resolvedTheme: 'light' | 'dark'
  setTheme: (mode: ThemeMode) => void
}

const THEME_STORAGE_KEY = 'resqsense_theme'

const ThemeContext = createContext<ThemeContextType>({
  theme: 'system',
  resolvedTheme: 'dark',
  setTheme: () => {},
})

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<ThemeMode>(() => {
    try {
      const saved = localStorage.getItem(THEME_STORAGE_KEY) as ThemeMode
      if (saved === 'light' || saved === 'dark' || saved === 'system') {
        return saved
      }
    } catch {
      // fallback
    }
    return 'system'
  })

  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>('dark')

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

    const computeResolved = (mode: ThemeMode): 'light' | 'dark' => {
      if (mode === 'system') {
        return mediaQuery.matches ? 'dark' : 'light'
      }
      return mode
    }

    const currentResolved = computeResolved(theme)
    setResolvedTheme(currentResolved)
    document.documentElement.setAttribute('data-theme', currentResolved)

    const handleChange = () => {
      if (theme === 'system') {
        const nextResolved = computeResolved('system')
        setResolvedTheme(nextResolved)
        document.documentElement.setAttribute('data-theme', nextResolved)
      }
    }

    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [theme])

  const setTheme = (mode: ThemeMode) => {
    setThemeState(mode)
    try {
      localStorage.setItem(THEME_STORAGE_KEY, mode)
    } catch {
      // ignore storage errors
    }
  }

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => useContext(ThemeContext)
