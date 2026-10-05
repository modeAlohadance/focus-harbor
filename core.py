"""Monotonic countdown and persistent completed sessions."""
import csv
import sqlite3
import time
from datetime import datetime


class Countdown:
    def __init__(self, seconds=1500, clock=time.monotonic):
        self.clock = clock
        self.reset(seconds)

    def reset(self, seconds):
        if seconds <= 0:
            raise ValueError('Длительность должна быть положительной.')
        self.duration = float(seconds)
        self.left = float(seconds)
        self.deadline = None

    @property
    def running(self):
        return self.deadline is not None

    def remaining(self):
        return max(0.0, self.deadline - self.clock()) if self.running else self.left

    def start(self):
        if not self.running and self.left > 0:
            self.deadline = self.clock() + self.left

    def pause(self):
        self.left = self.remaining()
        self.deadline = None

    def finish(self):
        if self.running and self.remaining() == 0:
            self.pause()
            return True
        return False


class Journal:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY, ended TEXT NOT NULL, task TEXT NOT NULL, seconds INTEGER NOT NULL)')
        self.db.commit()

    def add(self, task, seconds):
        with self.db:
            self.db.execute('INSERT INTO sessions (ended, task, seconds) VALUES (?, ?, ?)',
                            (datetime.now().isoformat(timespec='seconds'), task, int(seconds)))

    def recent(self):
        return self.db.execute('SELECT ended, task, seconds FROM sessions ORDER BY id DESC LIMIT 500').fetchall()

    def today(self):
        return self.db.execute('SELECT COALESCE(SUM(seconds),0), COUNT(*) FROM sessions WHERE substr(ended,1,10)=?',
                               (datetime.now().date().isoformat(),)).fetchone()

    def export(self, path):
        with open(path, 'w', newline='', encoding='utf-8-sig') as out:
            writer = csv.writer(out)
            writer.writerow(['Завершено', 'Задача', 'Секунды'])
            for ended, task, seconds in self.db.execute('SELECT ended, task, seconds FROM sessions ORDER BY id'):
                # Treat user text as text when a spreadsheet opens this CSV.
                writer.writerow([ended, "'" + task if task.startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else task, seconds])

    def close(self):
        self.db.close()
