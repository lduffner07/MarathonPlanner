import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request

LAUNCHER = Path(__file__).resolve().parents[1] / 'marathon'


class LauncherTest(unittest.TestCase):
    def test_terminal_from_another_directory(self):
        result = subprocess.run([str(LAUNCHER), 'terminal'], cwd='/tmp', input='Runner\n30\n50\n16\n4\n0\n1\n0\n', capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Pace Chart', result.stdout)
        self.assertIn('Training session ended.', result.stdout)

    def test_invalid_port(self):
        result = subprocess.run([str(LAUNCHER), 'web', '--port', '99999'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Port must be between', result.stderr)

    def test_web_from_another_directory(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        with tempfile.TemporaryDirectory() as folder:
            process = subprocess.Popen([str(LAUNCHER), 'web', '--no-open', '--port', str(port)], cwd='/tmp', env={**os.environ, 'MARATHON_DB':folder+'/journal.sqlite3'}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                for attempt in range(40):
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=1) as response:
                            self.assertIn('One run at a time.', response.read().decode())
                        break
                    except OSError:
                        if process.poll() is not None:
                            self.fail(process.communicate()[1])
                        time.sleep(.05)
                else:
                    self.fail('Web launcher did not become ready')
            finally:
                process.terminate()
                process.communicate(timeout=5)
