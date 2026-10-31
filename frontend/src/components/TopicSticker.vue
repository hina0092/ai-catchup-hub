<script setup>
import { computed, useId } from 'vue'

const props = defineProps({ name: { type: String, required: true } })
const id = useId()
const outlines = {
  audio: 'M19 4h10v22h7v5l-8 5v4h7v4H13v-4h7v-4l-8-5V20h5V8Z',
  folder: 'M6 12h13l5 5h17v23H6Z',
  image: 'M23 5C10 5 4 15 5 26c1 11 12 17 22 16 9-1 2-8 7-11 11 2 13-7 8-16C38 8 31 5 23 5Z',
  code: 'M7 5h34v28H29v6h8v4H11v-4h8v-6H7Z',
  research: 'M18 5h13v5h-3v10l13 18c2 4-1 6-5 6H12c-4 0-7-2-5-6l13-18V10h-2Z',
  guide: 'M7 7h31l4 5v31H10l-3-4Z',
  globe: 'M24 4a17 17 0 0 1 6 33v3h8v4H10v-4h9v-3A17 17 0 0 1 24 4Z',
  ai: 'M24 4a20 20 0 1 1 0 40 20 20 0 0 1 0-40Z',
  chip: 'M22 3h4v7h10l7 7v20l-5 6H10l-5-6V17l7-7h10Z',
}
const kind = computed(() => Object.hasOwn(outlines, props.name) ? props.name : 'chip')
const mint = `url(#${id}-mint)`
const blue = `url(#${id}-blue)`
const lavender = `url(#${id}-lavender)`
</script>

<template>
  <svg class="topic-sticker" :data-kind="kind" width="48" height="48" viewBox="0 0 48 48" fill="none" aria-hidden="true" focusable="false">
    <defs>
      <linearGradient :id="id + '-mint'" x1="12" y1="8" x2="33" y2="42" gradientUnits="userSpaceOnUse"><stop stop-color="#DDFFF3"/><stop offset="1" stop-color="#78D4C0"/></linearGradient>
      <linearGradient :id="id + '-blue'" x1="9" y1="7" x2="36" y2="42" gradientUnits="userSpaceOnUse"><stop stop-color="#E7FAFF"/><stop offset="1" stop-color="#94C6E8"/></linearGradient>
      <linearGradient :id="id + '-lavender'" x1="12" y1="7" x2="34" y2="41" gradientUnits="userSpaceOnUse"><stop stop-color="#F0ECFF"/><stop offset="1" stop-color="#B7AEE9"/></linearGradient>
    </defs>
    <path :d="outlines[kind]" fill="white" stroke="white" stroke-width="6" stroke-linejoin="round" />
    <g stroke="#365775" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <template v-if="kind === 'audio'">
        <path d="M12 21v4a12 12 0 0 0 24 0v-4M24 37v6m-10 0h20" :stroke-width="3" />
        <rect x="17" y="5" width="14" height="27" rx="7" :fill="mint" />
        <path d="M21 11h6m-6 5h6m-6 5h6" stroke="#569C96" />
        <path d="M20 9v15" stroke="white" stroke-width="2" />
      </template>
      <template v-else-if="kind === 'folder'">
        <path d="M7 12h12l5 5h16v22H7Z" :fill="blue" />
        <path d="M6 21h36l-3 20H8Z" fill="#FFEDB7" />
        <path d="M11 25h25" stroke="white" stroke-width="2" />
        <rect x="16" y="29" width="15" height="6" rx="2" fill="#FFFDF0" stroke="#D0BA81" />
      </template>
      <template v-else-if="kind === 'image'">
        <path d="M23 5C10 5 4 15 5 26c1 11 12 17 22 16 9-1 2-8 7-11 11 2 13-7 8-16C38 8 31 5 23 5Z" fill="#FFF1CF" />
        <circle cx="14" cy="19" r="3" fill="#99DACB"/><circle cx="23" cy="13" r="3" fill="#A8D4F0"/><circle cx="33" cy="17" r="3" fill="#C5B9EC"/><circle cx="12" cy="29" r="3" fill="#F0C2CF"/>
        <path d="m24 29 11-8 4 4-11 8-5 2Z" :fill="blue"/><path d="m35 21 4 4" stroke="white"/>
      </template>
      <template v-else-if="kind === 'code'">
        <path d="M20 32h8v8h-8z" :fill="lavender"/><path d="M12 40h24v3H12z" :fill="blue"/>
        <rect x="6" y="5" width="36" height="29" rx="4" :fill="blue"/><rect x="10" y="9" width="28" height="20" rx="2" fill="#F6FFFC"/>
        <path d="m19 14-5 5 5 5m10-10 5 5-5 5m-4-11-3 14" stroke="#369F8B"/>
        <path d="M11 7h25" stroke="white"/>
      </template>
      <template v-else-if="kind === 'research'">
        <path d="M18 5h13v5h-3v10l13 18c2 4-1 6-5 6H12c-4 0-7-2-5-6l13-18V10h-2Z" :fill="blue" />
        <path d="m15 30-5 9c-.5 1 0 2 2 2h24c2 0 2.5-1 2-2l-5-9c-6 3-11-3-18 0Z" :fill="mint" stroke="#5DAE9C"/>
        <path d="M23 12v10l-8 13" stroke="white" stroke-width="2"/><circle cx="26" cy="34" r="2" fill="white" stroke="#8DC8B8"/><circle cx="30" cy="25" r="2" :fill="lavender"/>
      </template>
      <template v-else-if="kind === 'guide'">
        <path d="M7 7h29l5 5v30H10l-3-4Z" :fill="blue"/><path d="M12 7v31m0 0h29" stroke="#729EB7"/>
        <rect x="17" y="14" width="18" height="18" rx="3" fill="#F9FFFD"/><path d="m26 17 5 5-5 7-5-7 5-5Z" :fill="mint"/><path d="M8 9v25" stroke="white" stroke-width="2"/>
      </template>
      <template v-else-if="kind === 'globe'">
        <path d="M24 36v7m-10 0h20" stroke-width="3"/><circle cx="24" cy="21" r="17" :fill="blue"/>
        <ellipse cx="24" cy="21" rx="8" ry="17" stroke="#6BA8B7"/><path d="M8 16h32M8 26h32" stroke="#6BA8B7"/><path d="m15 10 5 3-2 7-5 1-3-6m20 8 7 2-2 8-6 1-3-6Z" :fill="mint"/>
      </template>
      <template v-else-if="kind === 'ai'">
        <circle cx="24" cy="24" r="20" :fill="lavender"/><path d="M7 15a19 19 0 0 1 32 18" :fill="blue" stroke="none"/><path d="M11 37a19 19 0 0 0 27-26" :fill="mint" stroke="none"/>
        <circle cx="24" cy="24" r="20"/><circle cx="24" cy="24" r="6" fill="#F4FCFF"/><circle cx="24" cy="24" r="2" fill="#94C6E8"/><path d="m14 9-5 6m26 18-5 5" stroke="white" stroke-width="3"/>
      </template>
      <template v-else>
        <path d="M24 6v7" stroke-width="3"/><circle cx="24" cy="5" r="3" :fill="mint"/>
        <rect x="5" y="16" width="5" height="18" rx="2" :fill="lavender"/><rect x="38" y="16" width="5" height="18" rx="2" :fill="lavender"/>
        <rect x="9" y="12" width="30" height="30" rx="7" :fill="blue"/><rect x="13" y="17" width="22" height="19" rx="5" fill="#F7FFFD"/>
        <path d="M18 23v4m12-4v4m-10 5h8" stroke="#3B7B84" stroke-width="2.5"/><path d="M14 14h17" stroke="white" stroke-width="2"/>
      </template>
    </g>
  </svg>
</template>
