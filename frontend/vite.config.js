import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { offlineBuild } from './offlineBuild.js'
export default defineConfig({ plugins: [vue(), offlineBuild()], base: './' })
