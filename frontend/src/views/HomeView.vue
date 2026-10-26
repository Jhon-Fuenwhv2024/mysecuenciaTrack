<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import MultitrackPlayer from '../components/MultitrackPlayer.vue'
import {
  createJob,
  exportUrl,
  getJob,
  updateMarkers,
  type Job,
  type Marker,
} from '../api'

const file = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const stemMode = ref<'4stems' | '6stems'>('4stems')
const targetBpm = ref<number | null>(null)
const transpose = ref(0)
const countIn = ref(1)
const voiceCues = ref(true)
const dragOver = ref(false)

const job = ref<Job | null>(null)
const busy = ref(false)
const error = ref<string | null>(null)
const markersDraft = ref<Marker[]>([])
const savingMarkers = ref(false)

let pollTimer: number | undefined

const canSubmit = computed(() => !!file.value && !busy.value)
const isReady = computed(() => job.value?.status === 'ready')
const isFailed = computed(() => job.value?.status === 'failed')
const isProcessing = computed(
  () =>
    !!job.value &&
    !['ready', 'failed', 'expired'].includes(job.value.status),
)

function onFileChange(ev: Event) {
  const input = ev.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
}

function onDrop(ev: DragEvent) {
  ev.preventDefault()
  dragOver.value = false
  const f = ev.dataTransfer?.files?.[0]
  if (f) file.value = f
}

async function submit() {
  if (!file.value) return
  error.value = null
  busy.value = true
  job.value = null
  try {
    const created = await createJob({
      file: file.value,
      stem_mode: stemMode.value,
      target_bpm: targetBpm.value,
      transpose_semitones: transpose.value,
      count_in_bars: countIn.value,
      generate_voice_cues: voiceCues.value,
    })
    job.value = created
    startPoll(created.id)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Error al subir'
  } finally {
    busy.value = false
  }
}

function startPoll(id: string) {
  stopPoll()
  pollTimer = window.setInterval(async () => {
    try {
      const fresh = await getJob(id)
      job.value = fresh
      if (fresh.status === 'ready') {
        markersDraft.value = structuredClone(fresh.markers ?? [])
        stopPoll()
      }
      if (fresh.status === 'failed' || fresh.status === 'expired') {
        stopPoll()
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error de estado'
      stopPoll()
    }
  }, 1500)
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = undefined
  }
}

async function saveMarkers() {
  if (!job.value) return
  savingMarkers.value = true
  error.value = null
  try {
    job.value = await updateMarkers(job.value.id, markersDraft.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'No se guardaron marcadores'
  } finally {
    savingMarkers.value = false
  }
}

function addMarker() {
  const last = markersDraft.value[markersDraft.value.length - 1]
  const start = last ? last.end : 0
  markersDraft.value.push({
    id: `sec-${Date.now()}`,
    label: 'marcador',
    start,
    end: start + 8,
    editable: true,
  })
}

onBeforeUnmount(stopPoll)
</script>

<template>
  <section class="hero">
    <h1>SecuenciaLive</h1>
    <p>
      Sube una canción y obtén stems, click sincronizado, conteo de entrada y
      marcadores listos para Ableton, Playback o tu set en vivo.
    </p>
    <div class="wave-deco" aria-hidden="true" />
  </section>

  <section class="panel">
    <h2>Nueva secuencia</h2>
    <p class="hint">
      MP3 o WAV. El audio original se borra tras procesar; el ZIP expira en 24 h.
    </p>

    <form class="grid-form" @submit.prevent="submit">
      <div
        class="dropzone"
        :class="{ active: dragOver }"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop="onDrop"
        @click="fileInput?.click()"
      >
        <strong>{{ file ? file.name : 'Arrastra tu canción aquí' }}</strong>
        <span>{{ file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : 'o haz clic para elegir archivo' }}</span>
        <input
          ref="fileInput"
          type="file"
          accept=".mp3,.wav,.flac,.ogg,.m4a,audio/*"
          hidden
          @change="onFileChange"
        />
      </div>

      <label class="field">
        Stems
        <select v-model="stemMode">
          <option value="4stems">4 pistas (voz, batería, bajo, otros)</option>
          <option value="6stems">6 pistas (+ guitarra y piano)</option>
        </select>
      </label>

      <label class="field">
        Tempo destino (BPM, opcional)
        <input v-model.number="targetBpm" type="number" min="40" max="240" placeholder="Auto" />
      </label>

      <label class="field">
        Transponer (semitonos)
        <input v-model.number="transpose" type="number" min="-12" max="12" />
      </label>

      <label class="field">
        Compases de conteo
        <select v-model.number="countIn">
          <option :value="0">Sin conteo</option>
          <option :value="1">1 compás</option>
          <option :value="2">2 compases</option>
        </select>
      </label>

      <label class="field">
        Cues de guía
        <select v-model="voiceCues">
          <option :value="true">Sí (tonos por sección)</option>
          <option :value="false">Solo marcadores</option>
        </select>
      </label>

      <div class="actions">
        <button class="btn btn-primary" type="submit" :disabled="!canSubmit">
          {{ busy ? 'Subiendo…' : 'Generar secuencia' }}
        </button>
        <a class="btn btn-ghost" href="/terminos">Derechos de autor</a>
      </div>
    </form>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="job" class="progress-wrap">
      <div class="meta-row">
        <span class="chip"><strong>Estado:</strong> {{ job.message || job.status }}</span>
        <span class="chip"><strong>{{ job.progress }}%</strong></span>
        <span v-if="job.bpm" class="chip"><strong>BPM</strong> {{ job.bpm }}</span>
        <span v-if="job.key" class="chip"><strong>Tono</strong> {{ job.key }}</span>
        <span v-if="job.time_signature" class="chip"><strong>Compás</strong> {{ job.time_signature }}</span>
      </div>
      <div class="progress-bar" style="margin-top: 0.85rem">
        <span :style="{ width: `${job.progress}%` }" />
      </div>
      <p v-if="isFailed" class="error">{{ job.error || 'El procesamiento falló' }}</p>
      <p v-if="isProcessing" class="hint" style="margin-top: 0.75rem">
        En CPU la separación con Demucs puede tardar varios minutos. En producción
        conviene GPU.
      </p>
    </div>
  </section>

  <section v-if="isReady && job" class="panel">
    <h2>Reproductor multitrack</h2>
    <p class="hint">Mute, solo y volumen por pista. Incluye click y guía.</p>
    <MultitrackPlayer :job="job" />
    <div class="actions" style="margin-top: 1rem">
      <a class="btn btn-primary" :href="exportUrl(job.id)" download>Descargar ZIP</a>
    </div>
  </section>

  <section v-if="isReady && markersDraft.length" class="panel">
    <h2>Marcadores de sección</h2>
    <p class="hint">Editables si la detección automática no encaja con tu arreglo.</p>
    <div class="markers">
      <div v-for="(m, idx) in markersDraft" :key="m.id" class="marker-row">
        <input v-model="m.label" placeholder="Etiqueta" />
        <input v-model.number="m.start" type="number" step="0.01" min="0" title="Inicio (s)" />
        <input v-model.number="m.end" type="number" step="0.01" min="0" title="Fin (s)" />
        <button
          v-if="false"
          type="button"
          @click="markersDraft.splice(idx, 1)"
        >
          Quitar
        </button>
      </div>
    </div>
    <div class="actions">
      <button class="btn btn-ghost" type="button" @click="addMarker">Añadir marcador</button>
      <button class="btn btn-primary" type="button" :disabled="savingMarkers" @click="saveMarkers">
        {{ savingMarkers ? 'Guardando…' : 'Guardar marcadores' }}
      </button>
    </div>
  </section>
</template>
