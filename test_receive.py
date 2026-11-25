import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import os
import receive


class ReceiverTests(unittest.TestCase):
    def test_repeat_and_newer_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / 'file.txt'
            state = root / 'partials'
            checkpoint = receive.Checkpoint(root / 'checkpoint.db')
            responses = [
                {'size': 3, 'last_modified': 'Wed, 21 Oct 2015 07:28:00 GMT', 'etag': None},
                {'size': 3, 'last_modified': 'Wed, 21 Oct 2015 07:28:00 GMT', 'etag': None},
                {'size': 3, 'last_modified': 'Wed, 21 Oct 2015 07:28:02 GMT', 'etag': None},
            ]
            class Response:
                status = 200
                headers = {}
                def __init__(self, data): self.data = data
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def read(self, size):
                    data, self.data = self.data, b''
                    return data
            with patch.object(receive, 'PARTIAL_DIRECTORY', state), patch.object(receive, 'get_remote_metadata', side_effect=responses) as head, patch.object(receive, 'urlopen', side_effect=[Response(b'old'), Response(b'new')]) as get:
                receive.download_file('http://example/file', target, checkpoint)
                self.assertEqual(target.read_bytes(), b'old')
                receive.download_file('http://example/file', target, checkpoint)
                self.assertEqual(target.read_bytes(), b'old')
                receive.download_file('http://example/file', target, checkpoint)
                self.assertEqual(target.read_bytes(), b'new')
                self.assertEqual(int(target.stat().st_mtime), 1445412482)
                self.assertEqual(head.call_count, 3)
                self.assertEqual(get.call_count, 2)
            checkpoint.close()

    def test_missing_source_date_keeps_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / 'file.txt'
            target.write_bytes(b'local')
            checkpoint = receive.Checkpoint(root / 'checkpoint.db')
            with patch.object(receive, 'PARTIAL_DIRECTORY', root / 'partials'), patch.object(receive, 'get_remote_metadata', return_value={'size': 5, 'last_modified': None, 'etag': None}), patch.object(receive, 'write_failure') as failure, patch.object(receive, 'urlopen') as get:
                receive.download_file('http://example/file', target, checkpoint)
                self.assertEqual(target.read_bytes(), b'local')
                failure.assert_called_once()
                get.assert_not_called()
            checkpoint.close()

if __name__ == '__main__':
    unittest.main()
