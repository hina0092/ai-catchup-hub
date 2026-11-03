<script setup>
import { computed } from 'vue'

const props = defineProps({ name: { type: String, required: true } })
// Each cell is one pixel; the feed and article list share these motifs.
const sprites = {
  audio: [
    '....dddd....', '...dwwwwd...', '...dwbbwd...', '...dwbbwd...',
    '...dwbbwd...', '.d.dwbbwd.d.', '.d.dwmmwd.d.', '.d..dddd..d.',
    '..d......d..', '...dddddd...', '.....dd.....', '...dddddd...',
  ],
  folder: [
    '............', '.ddddd......', '.dwwwddddd..', '.dwwwwwwwd..',
    '.dddddddddd.', '.dyyyyyyyyd.', '.dywwwwyyyd.', '.dyyyyyyyyd.',
    '.dyyyyyyyyd.', '.dyyyyyyyyd.', '.dddddddddd.', '............',
  ],
  image: [
    '....ddddd...', '..ddyyyyydd.', '.dyybbbyyyyd', 'dyyybbbyyyyd',
    'dmmmyyypppyd', 'dmmmyyypppyd', 'dyyyyyyyyyyd', 'dyyywwwyyyyd',
    '.dyywwwyddd.', '.dyyyyyd....', '..ddyyyd....', '....ddd.....',
  ],
  code: [
    '.dddddddddd.', '.dwwwwwwwwd.', '.dwbbbbbbwd.', '.dwbmbbmbwd.',
    '.dwmbbbbmwd.', '.dwbmbbmbwd.', '.dwbbbbbbwd.', '.dwwwwwwwwd.',
    '.dddddddddd.', '.....dd.....', '...ddwwdd...', '..dddddddd..',
  ],
  research: [
    '....dddd....', '....dwwd....', '....dwwd....', '....dwwd....',
    '...dwwwwd...', '...dwbwwd...', '..dwwwwwwd..', '..dmmmmmmd..',
    '.dmmwmmmmmd.', '.dmmmmwmmmd.', '.dmmmmmmmmd.', '..dddddddd..',
  ],
  guide: [
    '..dddddddd..', '.dbwwwwwwwd.', '.dbwbbbbbwd.', '.dbwbwwwbwd.',
    '.dbwbwmwbwd.', '.dbwbwwwbwd.', '.dbwbbbbbwd.', '.dbwwwwwwwd.',
    '.dbwwwwwwwd.', '.dddddddddd.', '.dwwwwwwwwd.', '..ddddddddd.',
  ],
  globe: [
    '....dddd....', '..ddbbbbdd..', '.dbbmmmbbbd.', '.dbmmmmbbbd.',
    'dbbmmmbbbbbd', 'dbbbbbmmmbbd', 'dbbbbbmmmbbd', '.dbbbbmmmbd.',
    '.dbbbbbbbbd.', '..dddddddd..', '.....dd.....', '...dddddd...',
  ],
  ai: [
    '....dddd....', '..ddlllldd..', '.dllwwlllld.', '.dlwwllllld.',
    'dllwlmmlllld', 'dlllmddmllld', 'dbbbmddmbbbd', 'dbbbbmmbbbbd',
    '.dbbbbbbbbd.', '.dbbbbwwbbd.', '..ddbbbbdd..', '....dddd....',
  ],
  chip: [
    '.....mm.....', '.....dd.....', '..dddddddd..', '.dbbbbbbbbd.',
    'ddwwwwwwwwdd', 'dbwddwwddwbd', 'dbwddwwddwbd', 'dbwwwwwwwwbd',
    'ddwwddddwwdd', '.dbwwwwwwbd.', '.dbbbbbbbbd.', '..dddddddd..',
  ],
}
const palette = { d: '#36516B', w: '#F7FFFD', b: '#8ABDE3', m: '#50C5AA', l: '#BCB0E9', p: '#F2AFC8', y: '#F6D98D' }
const backgrounds = { audio: '#C5EDE1', folder: '#D3E8FA', image: '#F4DFEB', code: '#D5DDF6', research: '#C9EBEE', guide: '#E4DDF5', globe: '#D0EEDB', ai: '#DCE0F9', chip: '#D0EAF8' }
const kind = computed(() => Object.hasOwn(sprites, props.name) ? props.name : 'chip')
const pixels = computed(() => sprites[kind.value].flatMap((row, y) => [...row].flatMap((cell, x) => palette[cell] ? [{ x: x + 2, y: y + 2, fill: palette[cell] }] : [])))
</script>

<template>
  <svg class="topic-sticker" :data-kind="kind" width="48" height="48" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
    <rect width="16" height="16" rx="3" :fill="backgrounds[kind]" />
    <g shape-rendering="crispEdges">
      <rect v-for="pixel in pixels" :key="`${pixel.x}-${pixel.y}`" :x="pixel.x" :y="pixel.y" width="1" height="1" :fill="pixel.fill" />
    </g>
  </svg>
</template>
