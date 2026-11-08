import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const root = fileURLToPath(new URL('.', import.meta.url))
export function offlineBuild() {
  return {
    name: 'techmin-offline',
    enforce: 'post',
    generateBundle(options, bundle) {
      const resources = Object.keys(bundle).filter(name => !name.endsWith('.map')).sort()
      const brand = ['discover-pc.svg', 'saved-folder.svg', 'mint-loppy-game.jpg',
        ...[16, 32, 48, 180, 192, 512].map(size => `icon-${size}.png`)].map(name => `brand/${name}`).sort()
      const publicFiles = ['site.webmanifest', ...brand]
      const hash = createHash('sha256')
      const template = readFileSync(resolve(root, 'sw-template.js'), 'utf8')
      hash.update(template)
      for (const name of resources) {
        const item = bundle[name]
        hash.update(name).update(item.type === 'chunk' ? item.code : item.source)
      }
      for (const name of publicFiles) hash.update(name).update(readFileSync(resolve(root, 'public', name)))
      const source = template.replace('__BUILD_VERSION__', JSON.stringify(hash.digest('hex').slice(0, 20)))
        .replace('__PRECACHE__', JSON.stringify([...resources, ...publicFiles]))
      this.emitFile({ type: 'asset', fileName: 'sw.js', source })
    },
  }
}
