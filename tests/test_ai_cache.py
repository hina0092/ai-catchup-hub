import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from tools.ai_cache import GitCache, git

class DurableCacheTests(unittest.TestCase):
    def test_persist_restore_and_conflict_never_overwrites_remote(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict('os.environ', {'GH_TOKEN':''}):
            root=Path(temp); remote=root/'remote.git'; remote.mkdir()
            git(remote,'init','--bare')
            first=root/'first'; first.mkdir(); git(first,'init'); git(first,'checkout','--orphan','ai-cache')
            git(first,'remote','add','origin',str(remote))
            ledger=GitCache(first); ledger.save({'format':1,'entries':{},'attempts':{}})
            second=root/'second'
            subprocess.run(['git','clone','--branch','ai-cache',str(remote),str(second)],check=True,capture_output=True)
            self.assertEqual(GitCache(second).load(),ledger.load())
            data=ledger.load(); data['attempts']['https://example.com/a']='2026-10-22'; ledger.save(data)
            other=GitCache(second).load(); other['attempts']['https://example.com/b']='2026-10-22'
            with self.assertRaises(OSError): GitCache(second).save(other)
            remote_data=json.loads(git(remote,'show','ai-cache:enrichment.json').stdout)
            self.assertIn('https://example.com/a',remote_data['attempts'])
            self.assertNotIn('https://example.com/b',remote_data['attempts'])

    def test_wrong_branch_rejected(self):
        with patch('tools.ai_cache.git',return_value=type('Result',(),{'stdout':'main\n'})()):
            with self.assertRaises(ValueError): GitCache('.').save({})
