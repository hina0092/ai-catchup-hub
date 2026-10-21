<script setup>
import { feedTabs } from '../feed.js'
defineProps({modelValue:{type:String,default:'recommended'},savedCount:{type:Number,default:0}})
defineEmits(['update:modelValue'])
</script>
<template>
  <nav class="feed-tabs" aria-label="フィードの切り替え"><button v-for="[id,label] in feedTabs" :key="id" :aria-pressed="modelValue===id" :class="{active:modelValue===id}" @click="$emit('update:modelValue',id)">{{ label }}<span v-if="id==='saved'"> {{ savedCount }}</span></button></nav>
</template>
<style scoped>
.feed-tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;border-bottom:1px solid #dce3d9;margin-top:20px}.feed-tabs button{border:0;border-bottom:3px solid transparent;border-radius:6px 6px 0 0;background:transparent;padding:14px 4px;min-height:48px;color:#667662;font-size:13px}.feed-tabs button.active{color:#294a34;background:#e8eee3;border-bottom-color:#34543e;font-weight:700}.feed-tabs button span{font-size:11px}@media(max-width:400px){.feed-tabs button{font-size:11px}}
</style>
