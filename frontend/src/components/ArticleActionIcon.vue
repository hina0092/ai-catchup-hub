<script setup>
defineProps({ name: { type: String, required: true } })
</script>

<template>
  <svg class="action-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <path v-if="name === 'conversation'" d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8z" />
    <path v-else-if="name === 'bookmark'" d="M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16l-6-4z" />
    <template v-else-if="name === 'ai'">
      <path d="m12 3 2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3z" />
      <path d="M20 2v4m-2-2h4" />
    </template>
    <template v-else-if="name === 'audio'">
      <rect x="9" y="3" width="6" height="12" rx="3" />
      <path d="M5 11v1a7 7 0 0 0 14 0v-1M12 19v3m-4 0h8" />
    </template>
    <template v-else-if="name === 'article'">
      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Z" />
      <path d="M14 3v6h6M8 13h8m-8 4h5" />
    </template>
    <path v-else-if="name === 'folder'" d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7h18" />
    <template v-else-if="name === 'image'">
      <rect x="3" y="3" width="18" height="18" rx="3" />
      <circle cx="8" cy="8" r="1.5" /><path d="m3 17 5-5 4 4 4-6 5 7" />
    </template>
    <path v-else-if="name === 'code'" d="m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18" />
    <template v-else-if="name === 'search'">
      <circle cx="10.5" cy="10.5" r="7" /><path d="m16 16 5 5" />
    </template>
    <template v-else-if="name === 'idea'">
      <path d="M8 16c0-3-3-3.5-3-7a7 7 0 0 1 14 0c0 3.5-3 4-3 7M8 17h8m-7 4h6M12 2V0" />
    </template>
    <template v-else-if="name === 'info'">
      <circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7h.01" />
    </template>
    <path v-else-if="name === 'refresh'" d="M20 7a9 9 0 1 0 1 8M20 2v6h-6" />
    <template v-else-if="name === 'user'">
      <circle cx="12" cy="8" r="4" /><path d="M4 22v-2a8 8 0 0 1 16 0v2" />
    </template>
    <template v-else-if="name === 'copy'">
      <rect x="8" y="8" width="13" height="13" rx="2" /><path d="M16 4V3H3v13h1" />
    </template>
    <template v-else>
      <rect x="5" y="5" width="14" height="14" rx="3" /><rect x="9" y="9" width="6" height="6" rx="1" />
      <path d="M8 2v3m8-3v3M8 19v3m8-3v3M2 8h3m-3 8h3M19 8h3m-3 8h3" />
    </template>
  </svg>
</template>
