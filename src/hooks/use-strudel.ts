/**
 * =============================================================================
 * USE STRUDEL HOOK
 * =============================================================================
 *
 * A custom React hook that manages the Strudel REPL lifecycle.
 * Handles script loading, playback state, editor control, and real-time
 * sync with the server via Server-Sent Events.
 *
 * USAGE:
 * ```tsx
 * const { loaded, isPlaying, editorRef, play, stop } = useStrudel()
 * ```
 *
 * RETURNS:
 * - loaded: boolean     - Whether the Strudel script has loaded
 * - isPlaying: boolean  - Whether audio is currently playing
 * - editorRef: ref      - Ref to attach to the strudel-editor element
 * - play: () => void    - Start/update playback
 * - stop: () => void    - Stop playback
 */

import { useEffect, useState, useRef, useCallback } from 'react'

/**
 * CDN URL for the Strudel REPL web component. Pinned: @latest changes the
 * sound under us without notice. In 1.3.0 `supersaw` goes silent after its
 * first note; re-test it before bumping.
 */
const STRUDEL_CDN = 'https://unpkg.com/@strudel/repl@1.3.0'

type ServerState = {
  code: string
  isPlaying: boolean
}

/**
 * Custom hook for managing the Strudel REPL.
 */
export function useStrudel() {
  const [loaded, setLoaded] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const editorRef = useRef<HTMLElement>(null)

  // Track last known server state to detect changes
  const lastServerStateRef = useRef<ServerState | null>(null)

  // Callback ref for when playback stops (used by audio recorder)
  const onStopCallbackRef = useRef<(() => void) | null>(null)

  /**
   * Load the Strudel script on mount.
   * The script registers the <strudel-editor> web component globally.
   */
  useEffect(() => {
    const script = document.createElement('script')
    script.src = STRUDEL_CDN
    script.onload = () => setLoaded(true)
    document.head.appendChild(script)
  }, [])

  /**
   * Browsers start audio suspended until a user gesture, and API-triggered
   * play is not one. Resume Strudel's AudioContext on any click or key press.
   */
  useEffect(() => {
    const unlock = () => (window as any).getAudioContext?.().resume()
    document.addEventListener('pointerdown', unlock)
    document.addEventListener('keydown', unlock)
    return () => {
      document.removeEventListener('pointerdown', unlock)
      document.removeEventListener('keydown', unlock)
    }
  }, [])

  /**
   * Get the editor instance from the ref.
   */
  const getEditor = useCallback(() => {
    const el = editorRef.current as any
    return el?.editor
  }, [])

  /**
   * Start or update playback.
   * Evaluates the current code in the editor.
   */
  const play = useCallback(async () => {
    const editor = getEditor()
    if (editor) {
      await editor.evaluate()
      setIsPlaying(true)
    }
  }, [getEditor])

  /**
   * Stop all audio playback.
   * Also calls the onStopCallback if registered (used by audio recorder).
   */
  const stop = useCallback(() => {
    const editor = getEditor()
    if (editor) {
      editor.stop()
      setIsPlaying(false)
      // Notify any registered callback (e.g., audio recorder)
      if (onStopCallbackRef.current) {
        onStopCallbackRef.current()
      }
    }
  }, [getEditor])

  /**
   * Register a callback to be called when playback stops.
   * Used by the audio recorder to auto-stop recording.
   */
  const setOnStopCallback = useCallback((callback: (() => void) | null) => {
    onStopCallbackRef.current = callback
  }, [])

  /**
   * Subscribe to Server-Sent Events for real-time state sync.
   * When the server state changes (via API), update the editor accordingly.
   */
  useEffect(() => {
    if (!loaded) return

    let eventSource: EventSource | null = null
    let timer: ReturnType<typeof setTimeout> | undefined

    // The web component creates its editor after upgrade. A message handled
    // before then would be recorded as applied but dropped, so connect only
    // once the editor exists. ponytail: 100ms poll, no readiness event known.
    const connect = () => {
      if (!getEditor()) {
        timer = setTimeout(connect, 100)
        return
      }
      eventSource = new EventSource('/api/events')
      eventSource.onmessage = onMessage
      // One-shot commands go out as DOM events; useAudioRecorder listens for 'strudel:record'
      eventSource.addEventListener('record', (e) =>
        window.dispatchEvent(new CustomEvent('strudel:record', { detail: JSON.parse((e as MessageEvent).data) })))
    }

    const onMessage = (event: MessageEvent) => {
      const newState: ServerState = JSON.parse(event.data)
      const lastState = lastServerStateRef.current
      // First message counts as a change, so a fresh page adopts the server's state
      const codeChanged = !lastState || newState.code !== lastState.code
      const playStateChanged = !lastState || newState.isPlaying !== lastState.isPlaying

      // Update code if changed
      if (codeChanged) {
        const editor = getEditor()
        if (editor) {
          editor.setCode(newState.code)
        }
      }

      // Evaluate if:
      // 1. Code changed AND server says we should be playing, OR
      // 2. Play state just changed to true
      if ((codeChanged && newState.isPlaying) || (playStateChanged && newState.isPlaying)) {
        play()
      } else if (playStateChanged && !newState.isPlaying) {
        stop()
      }

      lastServerStateRef.current = newState
    }

    // No onerror handler: EventSource reconnects by itself unless closed.
    connect()

    return () => {
      clearTimeout(timer)
      eventSource?.close()
    }
  }, [loaded, getEditor, play, stop])

  return {
    loaded,
    isPlaying,
    editorRef,
    play,
    stop,
    getEditor,
    setOnStopCallback,
  }
}
