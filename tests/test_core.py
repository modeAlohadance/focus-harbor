import csv
import tempfile
import unittest
from pathlib import Path
from core import Countdown, Journal


class Tests(unittest.TestCase):
    def test_pause_resume_and_single_finish(self):
        now = [10]
        timer = Countdown(60, lambda: now[0])
        timer.start()
        now[0] = 30
        timer.pause()
        now[0] = 100
        self.assertEqual(timer.remaining(), 40)
        timer.start()
        timer.start()
        now[0] = 141
        self.assertTrue(timer.finish())
        self.assertFalse(timer.finish())
        self.assertEqual(timer.remaining(), 0)

    def test_reset_and_invalid_duration(self):
        timer = Countdown(10)
        timer.start()
        timer.reset(20)
        self.assertFalse(timer.running)
        self.assertEqual(timer.remaining(), 20)
        with self.assertRaises(ValueError):
            timer.reset(0)

    def test_persistence_stats_and_safe_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'db'
            journal = Journal(path)
            journal.add('=1+1', 60)
            journal.add('Задача, с запятой', 120)
            self.assertEqual(journal.today(), (180, 2))
            journal.close()
            journal = Journal(path)
            self.assertEqual(len(journal.recent()), 2)
            export = Path(tmp) / 'out.csv'
            journal.export(export)
            with export.open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[1][1], "'=1+1")
            self.assertEqual(rows[2][1], 'Задача, с запятой')
            journal.close()
