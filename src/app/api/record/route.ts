/**
 * =============================================================================
 * RECORD API ENDPOINT
 * =============================================================================
 *
 * POST /api/record {"seconds": 240}
 * Connected pages record their audio output for that long, then upload the
 * WAV to /api/recording, which saves it in output/. The page must have had
 * one click since load (browsers keep audio suspended until then).
 */

import { NextResponse } from 'next/server'
import { state } from '../state'

export async function POST(request: Request) {
  const { seconds } = await request.json().catch(() => ({}))
  if (typeof seconds !== 'number' || !(seconds > 0 && seconds <= 900)) {
    return NextResponse.json({ error: 'seconds must be a number in (0, 900]' }, { status: 400 })
  }
  const pages = state.command('record', { seconds })
  if (pages === 0) {
    return NextResponse.json({ error: 'no page connected; open the REPL first' }, { status: 409 })
  }
  return NextResponse.json({ seconds, pages })
}
