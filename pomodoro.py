import tkinter as tk
from tkinter import font as tkfont
import threading
import winsound
import json
import os
from datetime import datetime
from PIL import Image, ImageDraw
import pystray

WORK_MIN    = 25
SHORT_MIN   = 5
LONG_MIN    = 15
LONG_AFTER  = 4

DURATIONS = {
    "work":        WORK_MIN  * 60,
    "short_break": SHORT_MIN * 60,
    "long_break":  LONG_MIN  * 60,
}

COLORS = {
    "bg":          "#1E1E2E",
    "surface":     "#2A2A3E",
    "work":        "#F38BA8",
    "short_break": "#A6E3A1",
    "long_break":  "#89DCEB",
    "text":        "#CDD6F4",
    "subtext":     "#6C7086",
    "button_fg":   "#1E1E2E",
}

MODE_LABELS = {
    "work":        "专注时间",
    "short_break": "短暂休息",
    "long_break":  "长休息",
}

DATA_FILE = os.path.join(os.path.dirname(__file__), "pomodoro_data.json")


def load_data():
    try:
        with open(DATA_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"today": "", "count": 0, "total": 0}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


def make_tray_icon(color_hex):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse([4, 4, 60, 60], fill=color_hex)
    return img


class PomodoroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("番茄钟")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        self.data = load_data()
        today = datetime.now().strftime("%Y-%m-%d")
        if self.data["today"] != today:
            self.data["today"] = today
            self.data["count"] = 0

        self.mode = "work"
        self.running = False
        self.remaining = DURATIONS["work"]
        self._timer_id = None
        self.tray = None
        self._last_tray_accent = None

        self._build_ui()
        self._update_display()
        self._start_tray()

    # ── UI construction ────────────────────────────────────
    def _build_ui(self):
        W = 340
        pad = 24

        mode_frame = tk.Frame(self.root, bg=COLORS["bg"])
        mode_frame.pack(pady=(pad, 0), padx=pad, fill="x")

        self.mode_btns = {}
        for m, label in MODE_LABELS.items():
            b = tk.Button(
                mode_frame, text=label, relief="flat", cursor="hand2",
                bg=COLORS["bg"], fg=COLORS["subtext"],
                font=("Microsoft YaHei UI", 9),
                padx=8, pady=4, bd=0,
                command=lambda m=m: self.set_mode(m),
            )
            b.pack(side="left", padx=2)
            self.mode_btns[m] = b

        task_frame = tk.Frame(self.root, bg=COLORS["surface"], bd=0)
        task_frame.pack(pady=(16, 0), padx=pad, fill="x")
        self.task_var = tk.StringVar(value="今天在做什么？")
        task_entry = tk.Entry(
            task_frame, textvariable=self.task_var,
            bg=COLORS["surface"], fg=COLORS["subtext"],
            insertbackground=COLORS["text"],
            relief="flat", font=("Microsoft YaHei UI", 10),
            bd=8,
        )
        task_entry.pack(fill="x")
        task_entry.bind("<FocusIn>",  lambda e: self._clear_placeholder(task_entry))
        task_entry.bind("<FocusOut>", lambda e: self._restore_placeholder(task_entry))

        self.canvas = tk.Canvas(
            self.root, width=W, height=W - 40,
            bg=COLORS["bg"], highlightthickness=0,
        )
        self.canvas.pack()

        cx, cy, r_outer = W // 2, (W - 40) // 2, 120

        self.canvas.create_arc(
            cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer,
            start=90, extent=359.99,
            outline=COLORS["surface"], width=16, style="arc",
            tags="bg_ring",
        )
        self.arc = self.canvas.create_arc(
            cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer,
            start=90, extent=0,
            outline=COLORS["work"], width=16, style="arc",
            tags="progress",
        )
        timer_font = tkfont.Font(family="Microsoft YaHei UI", size=48, weight="bold")
        self.timer_label = self.canvas.create_text(
            cx, cy - 10, text="25:00",
            fill=COLORS["text"], font=timer_font, tags="timer",
        )
        mode_font = tkfont.Font(family="Microsoft YaHei UI", size=11)
        self.mode_label = self.canvas.create_text(
            cx, cy + 44, text=MODE_LABELS["work"],
            fill=COLORS["subtext"], font=mode_font, tags="mode_text",
        )

        ctrl = tk.Frame(self.root, bg=COLORS["bg"])
        ctrl.pack(pady=(0, 8))

        self.start_btn = tk.Button(
            ctrl, text="开始", width=10, relief="flat", cursor="hand2",
            bg=COLORS["work"], fg=COLORS["button_fg"],
            font=("Microsoft YaHei UI", 12, "bold"),
            padx=16, pady=10, bd=0,
            command=self.toggle,
        )
        self.start_btn.pack(side="left", padx=6)

        reset_btn = tk.Button(
            ctrl, text="重置", width=6, relief="flat", cursor="hand2",
            bg=COLORS["surface"], fg=COLORS["text"],
            font=("Microsoft YaHei UI", 12),
            padx=12, pady=10, bd=0,
            command=self.reset,
        )
        reset_btn.pack(side="left", padx=6)

        stats = tk.Frame(self.root, bg=COLORS["surface"])
        stats.pack(fill="x", padx=pad, pady=(8, pad))

        tk.Label(stats, text="今日番茄", bg=COLORS["surface"],
                 fg=COLORS["subtext"], font=("Microsoft YaHei UI", 9)).pack(side="left", padx=12, pady=6)
        self.count_label = tk.Label(
            stats, text=f"🍅 {self.data['count']}",
            bg=COLORS["surface"], fg=COLORS["work"],
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.count_label.pack(side="left")

        self.total_label = tk.Label(
            stats, text=f"累计 {self.data['total']}",
            bg=COLORS["surface"], fg=COLORS["subtext"],
            font=("Microsoft YaHei UI", 9),
        )
        self.total_label.pack(side="right", padx=12, pady=6)

    # ── placeholder helpers ────────────────────────────────
    def _clear_placeholder(self, entry):
        if self.task_var.get() == "今天在做什么？":
            self.task_var.set("")
            entry.config(fg=COLORS["text"])

    def _restore_placeholder(self, entry):
        if not self.task_var.get():
            self.task_var.set("今天在做什么？")
            entry.config(fg=COLORS["subtext"])

    # ── mode switching ─────────────────────────────────────
    def set_mode(self, mode):
        if self.running:
            self.toggle()
        self._apply_mode(mode)

    def _apply_mode(self, mode):
        self.mode = mode
        self.remaining = DURATIONS[mode]
        self._update_display()

    def _accent(self):
        return COLORS[self.mode]

    # ── timer logic ────────────────────────────────────────
    def toggle(self):
        if self.running:
            self.running = False
            self.start_btn.config(text="继续")
            if self._timer_id:
                self.root.after_cancel(self._timer_id)
        else:
            self.running = True
            self.start_btn.config(text="暂停")
            self._tick()

    def reset(self):
        self.running = False
        if self._timer_id:
            self.root.after_cancel(self._timer_id)
        self.remaining = DURATIONS[self.mode]
        self.start_btn.config(text="开始")
        self._update_display()

    def _tick(self):
        if not self.running:
            return
        if self.remaining > 0:
            self.remaining -= 1
            self._update_display()
            self._timer_id = self.root.after(1000, self._tick)
        else:
            self._on_complete()

    def _on_complete(self):
        self.running = False
        self.start_btn.config(text="开始")
        self._play_sound()

        if self.mode == "work":
            self.data["count"] += 1
            self.data["total"] += 1
            save_data(self.data)
            self.count_label.config(text=f"🍅 {self.data['count']}")
            self.total_label.config(text=f"累计 {self.data['total']}")
            next_mode = "long_break" if self.data["count"] % LONG_AFTER == 0 else "short_break"
        else:
            next_mode = "work"
        self._apply_mode(next_mode)

    def _play_sound(self):
        threading.Thread(
            target=lambda: winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS),
            daemon=True,
        ).start()

    # ── display update ─────────────────────────────────────
    def _update_display(self):
        mins, secs = divmod(self.remaining, 60)
        time_str = f"{mins:02d}:{secs:02d}"
        self.canvas.itemconfig(self.timer_label, text=time_str)
        self.canvas.itemconfig(self.mode_label, text=MODE_LABELS[self.mode])

        fraction = 1 - (self.remaining / DURATIONS[self.mode])
        accent = self._accent()
        self.canvas.itemconfig(self.arc, extent=-fraction * 359.99, outline=accent)

        for m, b in self.mode_btns.items():
            if m == self.mode:
                b.config(fg=accent, font=("Microsoft YaHei UI", 9, "bold"))
            else:
                b.config(fg=COLORS["subtext"], font=("Microsoft YaHei UI", 9))

        self.start_btn.config(bg=accent)

        if self.tray and accent != self._last_tray_accent:
            self.tray.icon = make_tray_icon(accent)
            self._last_tray_accent = accent

        self.root.title(f"{time_str} — {MODE_LABELS[self.mode]}")

    # ── system tray ────────────────────────────────────────
    def _start_tray(self):
        icon_img = make_tray_icon(COLORS["work"])
        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", self._show_window, default=True),
            pystray.MenuItem("开始/暂停", lambda: self.root.after(0, self.toggle)),
            pystray.MenuItem("重置",     lambda: self.root.after(0, self.reset)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出",     self._quit),
        )
        self.tray = pystray.Icon("pomodoro", icon_img, "番茄钟", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    def minimize_to_tray(self):
        self.root.withdraw()

    def _show_window(self, icon=None, item=None):
        self.root.after(0, self.root.deiconify)

    def _quit(self, icon=None, item=None):
        self.running = False
        if self.tray:
            self.tray.stop()
        self.root.after(0, self.root.destroy)


if __name__ == "__main__":
    root = tk.Tk()
    app = PomodoroApp(root)
    root.mainloop()
