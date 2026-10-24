import { createApp } from 'vue'
import FeedView from './prototype/FeedView.vue'
import { trialStories } from './prototype/trialStories.js'
import './prototype/prototype.css'
createApp(FeedView, { stories: trialStories, publicMode: true }).mount('#app')
