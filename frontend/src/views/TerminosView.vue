<script setup lang="ts">
import { onMounted, ref } from 'vue'

const data = ref<{
  titulo?: string
  derechos_de_autor?: string
  responsabilidad?: string
  membresias?: string
} | null>(null)

onMounted(async () => {
  const res = await fetch('/api/terminos')
  data.value = await res.json()
})
</script>

<template>
  <section class="hero">
    <h1>Términos de uso</h1>
    <p>Transparencia sobre derechos de autor, retención de audio y membresías futuras.</p>
  </section>

  <section class="panel">
    <h2>{{ data?.titulo || 'Cargando…' }}</h2>
    <p class="hint">{{ data?.derechos_de_autor }}</p>
    <p class="hint">{{ data?.responsabilidad }}</p>
    <p class="hint">{{ data?.membresias }}</p>
    <p class="hint">
      SecuenciaLive es un proyecto de Jhon Fuentes (Colombia). No subas catálogos
      comerciales sin autorización. Los resultados del procesamiento son temporales.
    </p>
  </section>
</template>
