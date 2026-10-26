<script setup>
import { computed } from 'vue'

const props = defineProps({ story: { type:Object, required:true } })
const layout = computed(() => props.story.layout || 'combine')
const heading = computed(() => ({ steps:'処理の流れ', combine:'材料の組み合わせ', compare:'同じ観点で比較' })[layout.value])
const conclusion = computed(() => layout.value === 'compare' ? '違いのポイント' : '得られるもの')
</script>

<template>
  <figure v-if="story.inputs.length" class="visual story-diagram" :aria-label="story.question">
    <div class="visual-head"><span>{{ heading }}</span><span aria-hidden="true">✦</span></div>
    <p class="diagram-question">{{ story.question }}</p>
    <ol v-if="layout === 'steps'" class="diagram-steps" aria-label="処理の順番">
      <li v-for="(item, index) in story.inputs" :key="index">
        <span class="step-number" aria-hidden="true">{{ index + 1 }}</span><span>{{ item }}</span>
      </li>
    </ol>
    <ul v-else class="diagram-items" :class="layout" :aria-label="layout === 'compare' ? '比較する2つ' : '組み合わせる材料'">
      <li v-for="(item, index) in story.inputs" :key="index">{{ item }}</li>
    </ul>
    <div v-if="layout !== 'compare'" class="diagram-join"><span aria-hidden="true">↓</span><span v-if="layout === 'combine'">組み合わせる</span></div>
    <div class="diagram-conclusion"><span>{{ conclusion }}</span><p>{{ story.result }}</p></div>
    <figcaption>{{ story.diagramNote }}</figcaption>
  </figure>
</template>

<style scoped>
.diagram-question{font-size:14px;font-weight:600;margin:0 0 16px;line-height:1.7}
.diagram-steps,.diagram-items{list-style:none;padding:0;margin:0}
.diagram-steps{display:grid;gap:24px}
.diagram-steps li{display:flex;align-items:center;gap:10px;position:relative;background:var(--surface,#fff);border:1px solid var(--line);border-radius:8px;padding:12px;font-size:13px;line-height:1.7;overflow-wrap:anywhere}
.diagram-steps li:not(:last-child)::after{content:'↓';position:absolute;left:20px;bottom:-24px;height:24px;color:var(--muted)}
.step-number{display:grid;place-items:center;flex:0 0 24px;height:24px;border-radius:50%;background:var(--tone);font-size:12px}
.diagram-items{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.diagram-items li{background:var(--surface,#fff);border:1px solid var(--line);border-radius:8px;padding:12px;font-size:13px;line-height:1.8;overflow-wrap:anywhere}
.diagram-items.combine{display:flex;flex-wrap:wrap;gap:24px;justify-content:center}
.combine li{flex:1 1 100px;position:relative}
.combine li:not(:last-child)::after{content:'＋';position:absolute;right:-23px;top:50%;transform:translateY(-50%);width:22px;text-align:center;color:var(--muted)}
.diagram-join{display:flex;justify-content:center;align-items:center;gap:8px;padding:10px;font-size:12px;color:var(--muted)}
.diagram-join>span:first-child{font-size:20px}
.diagram-conclusion{background:var(--surface,#fff);border:1px solid var(--line);border-radius:8px;padding:12px}
.diagram-conclusion>span{font-size:11px;color:var(--muted)}
.diagram-conclusion p{font-size:14px;font-weight:600;line-height:1.8;margin:4px 0 0;overflow-wrap:anywhere}
.compare+.diagram-conclusion{margin-top:14px}
@media(max-width:400px){.diagram-items{grid-template-columns:1fr}.diagram-items.combine{display:grid;grid-template-columns:1fr;gap:24px}.combine li:not(:last-child)::after{right:auto;left:50%;top:auto;bottom:-24px;transform:translateX(-50%);height:24px}}
</style>
