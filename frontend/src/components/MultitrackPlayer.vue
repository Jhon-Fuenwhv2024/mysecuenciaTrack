<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { stemUrl, type Job } from '../api'

const props = defineProps<{ job: Job }>()

const trackNames = computed(() => {
  const stems = props.job.stems?.length
    ? props.job.stems
    : ['vocals', 'drums', 'bass', 'other']
  return ['click', 'guia', ...stems]
})

type TrackState = {
  name: string
  muted: boolean
  solo: boolean
  volume: number
  audio: HTMLAudioElement | null
  ready: boolean
  error: string | null
}

const tracks = ref<TrackState[]>([])
const playing = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const masterReady = ref(false)
const loadError = ref<string | null>(null)
let raf = 0

function buildTracks() {
  dispose()
  tracks.value = trackNames.value.map((name) => {
    const audio = new Audio(stemUrl(props.job.id, name))
    audio.preload = 'auto'
    audio.crossOrigin = 'anonymous'
    const state: TrackState = reactive({
      name,
      muted: name === 'guia',
      solo: false,
      volume: name === 'click' ? 0.7 : 0.9,
      audio,
      ready: false,
      error: null,
    })
    audio.volume = state.volume
    audio.addEventListener('canplaythrough', () => {
      state.ready = true
      if (Number.isFinite(audio.duration) && audio.duration > duration.value) {
        duration.value = audio.duration
      }
      masterReady.value = tracks.value.every((t) => t.ready || t.error)
    })
    audio.addEventListener('error', () => {
      state.error = 'No disponible'
      state.ready = true
      masterReady.value = tracks.value.every((t) => t.ready || t.error)
    })
    audio.addEventListener('ended', () => {
      if (tracks.value.every((t) => !t.audio || t.audio.ended || t.error)) {
        playing.value = false
      }
    })
    return state
  })
}

function applyMuteSolo() {
  const anySolo = tracks.value.some((t) => t.solo)
  for (const t of tracks.value) {
    if (!t.audio) continue
    const audible = anySolo ? t.solo : !t.muted
    t.audio.muted = !audible
    t.audio.volume = t.volume
  }
}

async function play() {
  applyMuteSolo()
  const startAt = currentTime.value
  await Promise.all(
    tracks.value.map(async (t) => {
      if (!t.audio || t.error) return
      t.audio.currentTime = startAt
      try {
        await t.audio.play()
      } catch {
        /* autoplay policies */
      }
    }),
  )
  playing.value = true
  tick()
}

function pause() {
  for (const t of tracks.value) t.audio?.pause()
  playing.value = false
  cancelAnimationFrame(raf)
}

function stop() {
  pause()
  currentTime.value = 0
  for (const t of tracks.value) {
    if (t.audio) t.audio.currentTime = 0
  }
}

function seek(ev: Event) {
  const value = Number((ev.target as HTMLInputElement).value)
  currentTime.value = value
  for (const t of tracks.value) {
    if (t.audio) t.audio.currentTime = value
  }
}

function tick() {
  const lead = tracks.value.find((t) => t.audio && !t.error)?.audio
  if (lead) currentTime.value = lead.currentTime
  if (playing.value) raf = requestAnimationFrame(tick)
}

function dispose() {
  cancelAnimationFrame(raf)
  for (const t of tracks.value) {
    t.audio?.pause()
    if (t.audio) {
      t.audio.src = ''
      t.audio = null
    }
  }
  tracks.value = []
  playing.value = false
  currentTime.value = 0
  duration.value = 0
  masterReady.value = false
  loadError.value = null
}

function fmt(sec: number) {
  if (!Number.isFinite(sec)) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

watch(
  () => props.job.id,
  () => buildTracks(),
  { immediate: true },
)

watch(
  tracks,
  () => applyMuteSolo(),
  { deep: true },
)

onBeforeUnmount(dispose)
</script>

<template>
  <div class="player">
    <div class="transport">
      <button class="btn btn-primary" :disabled="!masterReady" @click="playing ? pause() : play()">
        {{ playing ? 'Pausar' : 'Reproducir' }}
      </button>
      <button class="btn btn-ghost" @click="stop">Detener</button>
      <span class="chip">{{ fmt(currentTime) }} / {{ fmt(duration) }}</span>
      <span v-if="!masterReady" class="chip">Cargando pistas…</span>
    </div>

    <input
      type="range"
      min="0"
      :max="duration || 0"
      step="0.01"
      :value="currentTime"
      :disabled="!duration"
      @input="seek"
    />

    <div
      v-for="t in tracks"
      :key="t.name"
      class="track"
    >
      <div class="track-name">{{ t.name }}</div>
      <input
        type="range"
        min="0"
        max="1"
        step="0.01"
        v-model.number="t.volume"
        @input="applyMuteSolo"
      />
      <div class="track-controls">
        <button class="mini" :class="{ on: t.muted }" @click="t.muted = !t.muted; applyMuteSolo()">
          Mute
        </button>
        <button class="mini solo" :class="{ on: t.solo }" @click="t.solo = !t.solo; applyMuteSolo()">
          Solo
        </button>
      </div>
      <small v-if="t.error" class="error">{{ t.error }}</small>
    </div>
  </div>
</template>
