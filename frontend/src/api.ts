export type JobStatus =
  | 'queued'
  | 'uploading'
  | 'separating'
  | 'analyzing'
  | 'generating'
  | 'transforming'
  | 'exporting'
  | 'ready'
  | 'failed'
  | 'expired'

export interface Marker {
  id: string
  label: string
  start: number
  end: number
  editable?: boolean
}

export interface Job {
  id: string
  status: JobStatus
  progress: number
  message: string
  error?: string | null
  original_filename: string
  bpm?: number | null
  key?: string | null
  time_signature?: string | null
  duration_seconds?: number | null
  target_bpm?: number | null
  transpose_semitones: number
  stem_mode: string
  markers?: Marker[] | null
  analysis?: Record<string, unknown> | null
  stems?: string[] | null
  has_export: boolean
  created_at: string
  expires_at?: string | null
}

export interface CreateJobInput {
  file: File
  stem_mode: '4stems' | '6stems'
  target_bpm?: number | null
  transpose_semitones: number
  count_in_bars: number
  generate_voice_cues: boolean
  user_id?: string | null
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data.detail === 'string') return data.detail
    return JSON.stringify(data.detail ?? data)
  } catch {
    return res.statusText
  }
}

export async function createJob(input: CreateJobInput): Promise<Job> {
  const fd = new FormData()
  fd.append('file', input.file)
  fd.append('stem_mode', input.stem_mode)
  fd.append('transpose_semitones', String(input.transpose_semitones))
  fd.append('count_in_bars', String(input.count_in_bars))
  fd.append('generate_voice_cues', String(input.generate_voice_cues))
  if (input.target_bpm != null && !Number.isNaN(input.target_bpm)) {
    fd.append('target_bpm', String(input.target_bpm))
  }
  if (input.user_id) fd.append('user_id', input.user_id)

  const res = await fetch('/api/jobs', { method: 'POST', body: fd })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function getJob(id: string): Promise<Job> {
  const res = await fetch(`/api/jobs/${id}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function updateMarkers(id: string, markers: Marker[]): Promise<Job> {
  const res = await fetch(`/api/jobs/${id}/markers`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ markers }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export function exportUrl(id: string): string {
  return `/api/jobs/${id}/export`
}

export function stemUrl(id: string, stem: string): string {
  return `/api/jobs/${id}/stems/${encodeURIComponent(stem)}`
}

export async function getHealth() {
  const res = await fetch('/api/health')
  if (!res.ok) throw new Error('API no disponible')
  return res.json()
}
