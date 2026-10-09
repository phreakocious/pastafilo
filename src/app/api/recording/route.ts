/**
 * =============================================================================
 * RECORDING UPLOAD ENDPOINT
 * =============================================================================
 *
 * POST /api/recording (body: WAV bytes)
 * Saves the page's recording to output/ under a server-chosen name. Written
 * to a .part file and renamed, so a watcher never sees a half-written WAV.
 */

import { mkdir, rename, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { NextResponse } from 'next/server'
import { generateRecordingFilename } from '@/lib/wav-encoder'

const MAX_BYTES = 400 * 1024 * 1024 // 15 min of 16-bit 96 kHz stereo is ~346 MB

export async function POST(request: Request) {
  if (Number(request.headers.get('content-length')) > MAX_BYTES) {
    return NextResponse.json({ error: 'too large' }, { status: 413 })
  }
  const body = Buffer.from(await request.arrayBuffer())
  if (body.length > MAX_BYTES || body.toString('ascii', 0, 4) !== 'RIFF' || body.toString('ascii', 8, 12) !== 'WAVE') {
    return NextResponse.json({ error: 'expected a WAV body' }, { status: 400 })
  }
  const dir = path.join(process.cwd(), 'output')
  await mkdir(dir, { recursive: true })
  const file = path.join(dir, generateRecordingFilename())
  await writeFile(`${file}.part`, body)
  await rename(`${file}.part`, file)
  return NextResponse.json({ path: path.relative(process.cwd(), file), bytes: body.length })
}
