/**
 * =============================================================================
 * SHARED APPLICATION STATE WITH EVENT EMITTER
 * =============================================================================
 *
 * In-memory state for the Strudel REPL with Server-Sent Events support.
 * State changes are broadcast to all connected clients.
 */

import { DEFAULT_CODE } from '@/lib/constants'

export type AppState = {
  code: string
  isPlaying: boolean
}

type Listener = (state: AppState) => void
type CommandListener = (name: string, data: unknown) => void

/**
 * Simple event emitter for broadcasting state changes.
 */
class StateEmitter {
  private listeners: Set<Listener> = new Set()

  private _state: AppState = {
    code: DEFAULT_CODE,
    isPlaying: false,
  }

  get state(): AppState {
    return this._state
  }

  get code(): string {
    return this._state.code
  }

  set code(value: string) {
    this._state.code = value
    this.emit()
  }

  get isPlaying(): boolean {
    return this._state.isPlaying
  }

  set isPlaying(value: boolean) {
    this._state.isPlaying = value
    this.emit()
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private emit(): void {
    this.listeners.forEach(listener => listener(this._state))
  }

  private commandListeners: Set<CommandListener> = new Set()

  /**
   * One-shot command to connected pages (e.g. record). Not stored in state,
   * so a page that connects later never replays it. Returns the receiver count.
   */
  command(name: string, data: unknown): number {
    this.commandListeners.forEach(listener => listener(name, data))
    return this.commandListeners.size
  }

  subscribeCommands(listener: CommandListener): () => void {
    this.commandListeners.add(listener)
    return () => this.commandListeners.delete(listener)
  }
}

// Route handlers can each load their own copy of this module (seen in Next dev
// after an HMR update), and a module-level singleton then splits: /api/code
// accepts a push that /api/events never sees. Keep one instance per process.
// ponytail: edits to StateEmitter need a server restart to reach the live instance.
const globalForState = globalThis as unknown as { strudelState?: StateEmitter }
export const state = (globalForState.strudelState ??= new StateEmitter())
