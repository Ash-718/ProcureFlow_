import { Moon, Sun } from 'lucide-react'
import { useTheme } from './ThemeProvider'
import { Button } from '@/components/ui/button'

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === 'dark'

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={toggleTheme}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className="h-9 w-9 p-0 rounded-md border-border text-foreground hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring transition-colors"
    >
      {isDark ? (
        <Sun className="h-4 w-4 text-amber-400 transition-all" />
      ) : (
        <Moon className="h-4 w-4 text-slate-700 transition-all" />
      )}
      <span className="sr-only">{isDark ? 'Switch to light mode' : 'Switch to dark mode'}</span>
    </Button>
  )
}
