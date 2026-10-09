/**
 * =============================================================================
 * EVENTS API ENDPOINT (Server-Sent Events)
 * =============================================================================
 *
 * Streams state changes to connected clients in real-time.
 *
 * ENDPOINT:
 *   GET /api/events - Opens an SSE stream
 *
 * EVENTS:
 *   - state (default message): Fired when code or isPlaying changes
 *     data: { code: string, isPlaying: boolean }
 *   - record: One-shot command, never replayed on connect
 *     data: { seconds: number }
 */

import { state } from '../state'

export const dynamic = 'force-dynamic'

export async function GET() {
  const encoder = new TextEncoder()
  let unsubscribe: (() => void)[] = []
  let isClosed = false

  const stream = new ReadableStream({
    start(controller) {
      const send = (chunk: string) => {
        if (isClosed) return
        try {
          controller.enqueue(encoder.encode(chunk))
        } catch {
          // Controller closed, clean up
          isClosed = true
          unsubscribe.forEach(u => u())
        }
      }

      // Send initial state, then changes and commands
      send(`data: ${JSON.stringify(state.state)}\n\n`)
      unsubscribe = [
        state.subscribe((newState) => send(`data: ${JSON.stringify(newState)}\n\n`)),
        state.subscribeCommands((name, data) => send(`event: ${name}\ndata: ${JSON.stringify(data)}\n\n`)),
      ]
    },
    cancel() {
      // Called when client disconnects
      isClosed = true
      unsubscribe.forEach(u => u())
    },
  })

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  })
}
