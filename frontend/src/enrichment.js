const jp = /[\u3040-\u30ff\u3400-\u9fff]/
const text = (s,min,max) => typeof s==='string' && [...s.trim()].length>=min && [...s.trim()].length<=max && jp.test(s) && !/[<>]/.test(s)
export function enrichment(a) {
  if(a?.ai_status!=='completed' || !text(a.title_ja,1,300) || !text(a.summary_ja,1,250)) return null
  if(!Array.isArray(a.key_points)||a.key_points.length!==3||new Set(a.key_points).size!==3||!a.key_points.every(p=>text(p,30,60))) return null
  if(a.work_idea!=='直接的な業務活用例は未確認'&&!text(a.work_idea,100,200)) return null
  if(!['rss','article'].includes(a.source_basis)||!Number.isInteger(a.ai_version)||typeof a.ai_model!=='string'||typeof a.ai_generated_at!=='string') return null
  return {title_ja:jp.test(a.title)?a.title:a.title_ja,summary_ja:a.summary_ja,key_points:[...a.key_points],work_idea:a.work_idea,ai_status:'completed',ai_model:a.ai_model.slice(0,100),ai_version:a.ai_version,source_basis:a.source_basis,ai_generated_at:a.ai_generated_at.slice(0,80)}
}
