"""Dedicated ai-cache branch; conflicts stop generation, never force-push."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

def git(directory, *args, check=True):
    env = os.environ.copy()
    if env.get('GH_TOKEN'):
        env.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='http.https://github.com/.extraheader', GIT_CONFIG_VALUE_0='AUTHORIZATION: basic ' + base64.b64encode(('x-access-token:' + env['GH_TOKEN']).encode()).decode())
    try:
        result = subprocess.run(['git', '-C', str(directory), *args], env=env, capture_output=True, text=True, timeout=45)
    except subprocess.SubprocessError:
        raise OSError('cache git timed out') from None
    if check and result.returncode:
        raise OSError('cache git failed; no force push')
    return result

def setup(directory, repository, initialize=False):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('invalid repository')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    git(directory, 'init')
    git(directory, 'remote', 'add', 'origin', 'https://github.com/' + repository + '.git')
    result = git(directory, 'ls-remote', '--exit-code', 'origin', 'refs/heads/ai-cache', check=False)
    if result.returncode == 0:
        git(directory, 'fetch', '--depth=1', 'origin', 'refs/heads/ai-cache')
        git(directory, 'checkout', '-b', 'ai-cache', 'FETCH_HEAD')
    elif result.returncode == 2 and initialize:
        git(directory, 'checkout', '--orphan', 'ai-cache')
        GitCache(directory).save({'format': 1, 'entries': {}, 'attempts': {}})
    else:
        raise OSError('cache unavailable; explicit initialization required')

class GitCache:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'enrichment.json'

    def load(self):
        if git(self.directory, 'branch', '--show-current').stdout.strip() != 'ai-cache':
            raise ValueError('wrong branch')
        if self.path.stat().st_size > 20_000_000:
            raise ValueError('cache exceeds reviewed size')
        return json.loads(self.path.read_text(encoding='utf-8'))

    def save(self, cache):
        if git(self.directory, 'branch', '--show-current').stdout.strip() != 'ai-cache':
            raise ValueError('wrong branch')
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.directory, delete=False) as stream:
            temp = Path(stream.name)
            json.dump(cache, stream, ensure_ascii=False, sort_keys=True, indent=2)
        try:
            os.replace(temp, self.path)
        finally:
            temp.unlink(missing_ok=True)
        git(self.directory, 'add', '--', 'enrichment.json')
        if git(self.directory, 'diff', '--cached', '--quiet', check=False).returncode == 0:
            return
        git(self.directory, '-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com', 'commit', '-m', 'Persist AI cache and attempts [skip ci]')
        git(self.directory, 'push', 'origin', 'HEAD:refs/heads/ai-cache')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        setup(args.directory, os.environ['GITHUB_REPOSITORY'], os.environ.get('INITIALIZE_GEMINI_CACHE') == 'true')
    except (OSError, ValueError, KeyError):
        print('AI cache unavailable; generation disabled. Details redacted.')
        raise SystemExit(1)
