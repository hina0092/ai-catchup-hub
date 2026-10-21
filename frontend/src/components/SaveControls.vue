<script setup>
import { saveKinds } from '../savedArticles.js'
defineProps({article:{type:Object,required:true},labels:{type:Array,default:()=>[]}})
defineEmits(['toggle'])
</script>
<template>
  <div class="save-controls" role="group" :aria-label="article.title+' の保存区分'">
    <button v-for="[id,label] in saveKinds" :key="id" type="button" :aria-pressed="labels.includes(id)" :class="{active:labels.includes(id)}" @click="$emit('toggle',id)">{{ labels.includes(id)?'✓ ':'' }}{{ label }}</button>
  </div>
</template>
<style scoped>
.save-controls{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 18px}.save-controls button{min-height:44px;font-size:11px;padding:8px 10px;border:1px solid #ccd8c5;border-radius:8px;background:#fafcf7;color:#496046}.save-controls button.active{background:#34543e;color:#fff;border-color:#34543e}.save-controls button:hover{border-color:#34543e}
</style>
