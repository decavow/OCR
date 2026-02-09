import { useEffect } from 'react'

// Keyboard shortcuts (arrow keys for nav, Ctrl+C for copy)
export function useKeyboard(handlers: {
  onLeft?: () => void
  onRight?: () => void
  onCopy?: () => void
}) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Skip if user is typing in an input
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return
      }

      switch (e.key) {
        case 'ArrowLeft':
          e.preventDefault()
          handlers.onLeft?.()
          break
        case 'ArrowRight':
          e.preventDefault()
          handlers.onRight?.()
          break
        case 'c':
          if (e.ctrlKey || e.metaKey) {
            handlers.onCopy?.()
          }
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handlers])
}
