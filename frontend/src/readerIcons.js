// Presentation only: legacy cards and saved snapshots retain their original data.
const topicIcons = {
  '🎙️': 'audio', '🗂️': 'folder', '🎨': 'image', '💻': 'code',
  '🧩': 'chip', '🌏': 'globe', '⚡': 'ai', '✨': 'ai',
  '🔬': 'research', '🧭': 'guide', '🛠️': 'code',
}

export function topicIcon(story) {
  if (story.category?.includes('研究')) return 'research'
  return topicIcons[story.emoji] || 'chip'
}

export function readerLabel(text) {
  return text.replace(/^(?:\p{Extended_Pictographic}|\p{Emoji_Presentation})[\uFE0F\u200D\p{Extended_Pictographic}]*\s*/u, '')
}
