<script setup>
import commenters from '../commenters.json'

const props = defineProps({ name: { type: String, required: true } })
const avatars = import.meta.glob('../assets/commenters/*.webp', { eager: true, query: '?url', import: 'default' })
function avatarFor(name) {
  const person = commenters.find(person => person.name === name)
  return person ? avatars[`../assets/commenters/${person.avatar}`] : null
}
</script>

<template>
  <span class="comment-avatar" aria-hidden="true"><img v-if="avatarFor(props.name)" :src="avatarFor(props.name)" alt="" width="30" height="30" decoding="async"><span v-else>👤</span></span>
</template>
