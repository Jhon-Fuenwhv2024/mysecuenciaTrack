import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import TerminosView from './views/TerminosView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/terminos', name: 'terminos', component: TerminosView },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})
