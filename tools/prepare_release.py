"""Create an explicit allowlist source archive, without uploading or overwriting."""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'frontend/src/prototype/FeedView.vue', 'frontend/src/prototype/trialStories.js',
    'frontend/src/prototype/prototype.css', 'frontend/tests/public-feed.test.mjs',
    'collector/gemini.py', 'collector/gemini_config.json', 'collector/article_source.py',
    'tools/ai_cache.py', 'tests/test_gemini.py', 'tests/test_ai_cache.py',
    'frontend/src/enrichment.js', 'frontend/tests/enrichment.test.mjs',
    'frontend/src/feed.js', 'frontend/src/savedArticles.js', 'frontend/src/useSavedArticles.js',
    'frontend/src/components/FeedTabs.vue', 'frontend/src/components/SaveControls.vue',
    'frontend/tests/feed.test.mjs', 'frontend/tests/saved.test.mjs',
    'collector/analyze_discussions.py', 'collector/analysis_config.json',
    'tests/test_analysis.py', 'frontend/src/discussion.js',
    'frontend/src/components/DiscussionDetail.vue', 'frontend/tests/discussion.test.mjs',
    'collector/discussions.py', 'tests/test_discussions.py',
    '.gitignore', '.github/workflows/update.yml',
    'collector/translate.py', 'collector/translation_config.json',
    'tests/test_translation.py', 'frontend/tests/article-text.test.mjs',
    'frontend/src/components/ArticleText.vue',
    'collector/collect.py', 'collector/sources.json', 'collector/requirements.txt',
    'tests/test_collector.py', 'tests/test_release.py',
    'tests/fixtures/rss.xml', 'tests/fixtures/atom.xml',
    'tools/prepare_release.py', 'tools/public_feed.py',
    'frontend/.gitignore', 'frontend/index.html', 'frontend/package.json',
    'frontend/pnpm-lock.yaml', 'frontend/vite.config.js',
    'frontend/src/main.js', 'frontend/src/App.vue', 'frontend/src/style.css',
)


def prepare(destination, root=ROOT):
    destination = Path(destination)
    root = Path(root).resolve()
    paths = []
    for relative in FILES:
        path = root / relative
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f'Invalid release input: {relative}')
        paths.append((path, relative))
    if destination.exists():
        raise FileExistsError(destination)
    with ZipFile(destination, 'x', compression=ZIP_DEFLATED) as archive:
        for path, relative in paths:
            archive.write(path, relative)
        # A source repository starts with no feed contents; CI fetches fresh data.
        archive.writestr('frontend/public/data/articles.json', '[]\n')
        archive.writestr('README.md',
            '# AI Catchup Hub\n\n'
            'An illustrated AI-news feed with five editorial stories and clearly labeled fictional dialogue.\n\n'
            '## Local development\n\n'
            'Python 3.11+, Node.js 24 and pnpm 11.25.0.\n\n'
            '```sh\npython -m unittest discover -s tests -v\n'
            'python collector/collect.py --overwrite\n'
            'cd frontend\npnpm install --frozen-lockfile --ignore-scripts\npnpm dev\n```\n\n'
            '## Deployment\n\n'
            'Use a dedicated repository with main as the default branch. '
            'Select GitHub Actions in Settings > Pages. '
            'After approval, set the repository variable ENABLE_PAGES_DEPLOY to true. '
            'Run Test and publish editorial feed manually. '
            'The first public edition is fixed at 2026/10/24; collection and AI generation are not connected.\n\n'
            'Tests and build must succeed before deployment. '
            'The workflow uploads frontend/dist only and never commits generated data.\n')
    return len(paths) + 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(f'Prepared {prepare(args.destination)} files: {args.destination}')
