<script setup lang="ts">
</script>

<template>
  <div class="shell">
    <header class="nav">
      <router-link class="brand" to="/">Secuencia<span>Live</span></router-link>
      <nav class="nav-links">
        <router-link to="/">Crear secuencia</router-link>
        <router-link to="/terminos">Términos</router-link>
      </nav>
    </header>
    <router-view />
    <footer class="footer">
      <p>
        SecuenciaLive · Jhon Fuentes (Colombia) · Ingeniería de Software ·
        Multitracks para ensayo y vivo.
      </p>
    </footer>
  </div>
</template>
