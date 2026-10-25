"""Create an explicit allowlist source archive, without uploading or overwriting."""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'frontend/src/components/ArticleActionIcon.vue',
    'frontend/src/articleQuestion.js', 'frontend/src/components/AskAiDialog.vue',
    'frontend/tests/article-question.test.mjs',
    'frontend/src/readerSnapshots.js', 'frontend/tests/reader-saved.test.mjs',
    'README.md',
    '.github/workflows/card-trial.yml',
    'collector/card_trial.py', 'collector/card_grounding.py', 'collector/daily_cards.py',
    'collector/daily_config.json', 'tools/card_trial_remote.py', 'tools/daily_remote.py',
    'tools/render_card_trial.py', 'validation/card-inputs.json',
    'tests/test_card_trial.py', 'tests/test_card_grounding.py', 'tests/test_card_trial_remote.py',
    'tests/test_daily_cards.py', 'tests/test_daily_remote.py',
    'frontend/src/PublicFeed.vue', 'frontend/src/dailyStories.js', 'frontend/src/daily-feed.json',
    'frontend/tests/daily-feed.test.mjs',
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
            if relative == 'README.md':
                # Keep one README source; local notes stay outside the public archive.
                readme = path.read_text(encoding='utf-8').split('<!-- LOCAL_DOCS_START -->', 1)[0]
                archive.writestr(relative, readme.rstrip() + '\n')
            else:
                archive.write(path, relative)
        # Legacy RSS output is empty; daily cards are restored from the data branch.
        archive.writestr('frontend/public/data/articles.json', '[]\n')
    return len(paths) + 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(f'Prepared {prepare(args.destination)} files: {args.destination}')
