"""FocusHarbor desktop entry point."""
import math
import sqlite3
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog
from core import Countdown, Journal
from ui import style, table, data_path


class App:
    def __init__(self, root, path):
        self.root = root
        self.journal = Journal(path)
        self.timer = Countdown()
        self.phase = 'Работа'
        self.started = False
        self.task_snapshot = ''
        style(root, 'FocusHarbor — время для важного', '#7dd3fc')
        page = ttk.Frame(root, padding=24)
        page.pack(fill='both', expand=True)
        ttk.Label(page, text='FocusHarbor', style='Title.TLabel').pack(anchor='w')
        ttk.Label(page, text='Одна задача. Один спокойный отрезок времени.', style='Muted.TLabel').pack(anchor='w', pady=(0, 15))
        self.task = tk.StringVar()
        ttk.Label(page, text='Над чем работаем?').pack(anchor='w')
        self.task_entry = ttk.Entry(page, textvariable=self.task)
        self.task_entry.pack(fill='x', pady=6)
        controls = ttk.Frame(page)
        controls.pack(fill='x', pady=5)
        self.work = tk.StringVar(value='25')
        self.rest = tk.StringVar(value='5')
        self.duration_inputs = []
        for label, var in [('Работа, мин', self.work), ('Перерыв, мин', self.rest)]:
            ttk.Label(controls, text=label).pack(side='left', padx=(0, 8))
            widget = ttk.Spinbox(controls, from_=1, to=180, width=5, textvariable=var)
            widget.pack(side='left', padx=(0, 24))
            self.duration_inputs.append(widget)
        self.phase_label = ttk.Label(page, text=self.phase)
        self.phase_label.pack(pady=(12, 0))
        self.clock_label = ttk.Label(page, text='25:00', style='Clock.TLabel')
        self.clock_label.pack()
        buttons = ttk.Frame(page)
        buttons.pack(pady=5)
        self.start_button = ttk.Button(buttons, text='Начать', command=self.toggle)
        self.start_button.pack(side='left', padx=6)
        ttk.Button(buttons, text='Сбросить', command=self.reset).pack(side='left', padx=6)
        self.info = tk.StringVar(value='Нажмите «Начать», когда будете готовы.')
        ttk.Label(page, textvariable=self.info, style='Muted.TLabel', wraplength=850).pack(pady=10)
        row = ttk.Frame(page)
        row.pack(fill='x')
        self.stats = ttk.Label(row)
        self.stats.pack(side='left')
        ttk.Button(row, text='Экспорт CSV', command=self.export).pack(side='right')
        self.history = table(page, [('ended', 'Завершено', 190), ('task', 'Задача', 430), ('minutes', 'Минуты', 100)])
        self.refresh()
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.tick_id = root.after(100, self.tick)

    def durations(self):
        values = [int(self.work.get()), int(self.rest.get())]
        if not all(1 <= value <= 180 for value in values):
            raise ValueError()
        return values

    def toggle(self):
        if self.timer.running:
            self.timer.pause()
            self.start_button.configure(text='Продолжить')
            self.info.set('Пауза. Время не идёт.')
            return
        if not self.started:
            try:
                work, rest = self.durations()
            except ValueError:
                messagebox.showerror('Длительность', 'Введите целое число от 1 до 180 минут.', parent=self.root)
                return
            self.timer.reset((work if self.phase == 'Работа' else rest) * 60)
            self.task_snapshot = self.task.get().strip() or 'Без названия'
            self.started = True
            for widget in [self.task_entry, *self.duration_inputs]:
                widget.configure(state='disabled')
        self.timer.start()
        self.start_button.configure(text='Пауза')
        self.info.set('Сессия идёт.' if self.phase == 'Работа' else 'Время немного отдохнуть.')

    def reset(self):
        if self.started and not messagebox.askyesno('Сбросить таймер?', 'Текущая незавершённая сессия не попадёт в журнал.', parent=self.root):
            return
        self.prepare('Работа')
        self.info.set('Таймер сброшен.')

    def prepare(self, phase):
        self.phase = phase
        self.started = False
        try:
            work, rest = self.durations()
        except ValueError:
            work, rest = 25, 5
        self.timer.reset((work if phase == 'Работа' else rest) * 60)
        self.phase_label.configure(text=phase)
        self.start_button.configure(text='Начать')
        for widget in [self.task_entry, *self.duration_inputs]:
            widget.configure(state='normal')

    def tick(self):
        if self.timer.finish():
            self.root.bell()
            if self.phase == 'Работа':
                try:
                    self.journal.add(self.task_snapshot, self.timer.duration)
                    self.refresh()
                    self.info.set('Работа завершена и записана. Можно начать перерыв.')
                except sqlite3.Error as error:
                    messagebox.showerror('Журнал', f'Сессия завершена, но не сохранена: {error}', parent=self.root)
                self.prepare('Перерыв')
            else:
                self.prepare('Работа')
                self.info.set('Перерыв завершён. Следующую сессию начните, когда будете готовы.')
        left = math.ceil(self.timer.remaining())
        self.clock_label.configure(text=f'{left // 60:02}:{left % 60:02}')
        self.tick_id = self.root.after(150, self.tick)

    def refresh(self):
        self.history.delete(*self.history.get_children())
        for ended, task, seconds in self.journal.recent():
            self.history.insert('', 'end', values=(ended.replace('T', ' '), task, round(seconds / 60, 1)))
        seconds, count = self.journal.today()
        self.stats.configure(text=f'Сегодня: {count} сессий · {seconds // 60} мин фокусировки')

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '*.csv')], initialfile='focus-sessions.csv')
        if path:
            try:
                self.journal.export(path)
                self.info.set('Журнал экспортирован.')
            except (OSError, sqlite3.Error) as error:
                messagebox.showerror('Экспорт', str(error), parent=self.root)

    def close(self):
        if self.started and not messagebox.askyesno('Закрыть FocusHarbor?', 'Незавершённая сессия не сохранится. Закрыть приложение?', parent=self.root):
            return
        self.root.after_cancel(self.tick_id)
        self.journal.close()
        self.root.destroy()


def main():
    with tempfile.TemporaryDirectory(prefix='focus-smoke-') as tmp:
        smoke = '--smoke' in sys.argv
        root = tk.Tk()
        app = App(root, Path(tmp) / 'test.db' if smoke else data_path('FocusHarbor'))
        if smoke:
            app.task.set('Проверка интерфейса')
            app.toggle()
            app.toggle()
            app.prepare('Работа')
            root.after(300, app.close)
        root.mainloop()


if __name__ == '__main__':
    main()
