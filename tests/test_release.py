from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from tools.prepare_release import FILES, ROOT, prepare
from tools.public_feed import public_articles


class ReleaseTests(unittest.TestCase):
    def test_public_data_omits_excerpts_and_preserves_original(self):
        rows = [{'title': 'Title', 'summary': 'Excerpt', 'translation': {'title_ja': '翻訳'}}]
        self.assertNotIn('summary', public_articles(rows)[0])
        self.assertEqual(public_articles(rows)[0]['translation'], {'title_ja': '翻訳'})
        self.assertEqual(rows[0]['summary'], 'Excerpt')

    def test_archive_contains_only_allowlisted_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'source.zip'
            prepare(output)
            with ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()), set(FILES) | {'README.md', 'frontend/public/data/articles.json'})
                self.assertEqual(archive.read('frontend/public/data/articles.json'), b'[]\n')
                self.assertFalse(any('Handoff' in name or 'node_modules' in name for name in archive.namelist()))

    def test_existing_archive_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'source.zip'
            output.write_bytes(b'keep')
            with self.assertRaises(FileExistsError):
                prepare(output)
            self.assertEqual(output.read_bytes(), b'keep')

    def test_missing_input_creates_no_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'source.zip'
            with self.assertRaises(ValueError):
                prepare(output, root=folder)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
