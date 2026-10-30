"""Momo Desktop Pet — a small transparent, always-on-top Windows companion."""
from __future__ import annotations

import math
import random
import threading
import time
import tkinter as tk
from tkinter import ttk
from collections import deque

try:
    import soundcard as sc
except ImportError:
    sc = None
try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    np = Image = ImageDraw = ImageTk = None


ANIMALS = {
    "猫咪": ("🐱", "喵～", "呼噜呼噜", "猫猫正在看着你"),
    "狗狗": ("🐶", "汪！", "摇摇尾巴", "汪汪，陪你一会儿"),
    "兔兔": ("🐰", "蹦蹦！", "竖起耳朵", "今天也要元气满满"),
    "熊猫": ("🐼", "嗯？", "滚来滚去", "先休息一下吧"),
    "狐狸": ("🦊", "嘿嘿～", "甩甩尾巴", "发现一只认真工作的人"),
    "小鸭": ("🐥", "嘎嘎！", "扑腾翅膀", "嘎！一起听歌吧"),
}
MODES = {
    "陪伴": "会不时向你打招呼",
    "专注": "安静陪伴，减少打扰",
    "休息": "提醒你偶尔放松一下",
}


class DesktopPet:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Momo 桌面宠物")
        self.root.geometry("260x245+900+500")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#ff00ff")
        try:
            self.root.wm_attributes("-transparentcolor", "#ff00ff")
        except tk.TclError:
            self.root.configure(bg="#fff8f1")
        self.root.resizable(False, False)
        self.animal = tk.StringVar(value="猫咪")
        self.mode = tk.StringVar(value="陪伴")
        self.audio_on = False
        self.dancing = False
        self.level = 0.0
        self.audio_source = ""
        self.beat = 0.0
        self.low_history = deque(maxlen=24)
        self.last_beat = 0.0
        self.pet_frames = []
        self.dance_styles = ["自由律动", "弹跳", "左右摇摆", "转身", "踢踏", "派对"]
        self.dance_style = 0
        self.offset = 0
        self.clicks = 0
        self.drag = None
        self.bubble_until = 0
        self.status = tk.StringVar(value="准备好陪你啦")
        self.meter = tk.StringVar(value="音量  ░░░░░░░░░░")
        self.canvas = tk.Canvas(self.root, width=260, height=245, bg="#ff00ff",
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_oval(38, 192, 222, 224, fill="#000000", stipple="gray50", outline="", tags="shadow")
        self.make_pet_frames()
        self.pet_id = self.canvas.create_image(130, 142, image=self.pet_frames[len(self.pet_frames)//2], tags="pet")
        self.bubble_id = self.canvas.create_text(130, 42, text="", font=("Segoe UI", 12, "bold"),
                                                  fill="#49364b", tags="bubble")
        self.canvas.tag_bind("pet", "<Button-1>", self.pet_click)
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.move_drag)
        self.canvas.bind("<Button-3>", self.popup)
        self.canvas.bind("<Double-Button-1>", lambda _e: self.open_panel())
        self.root.bind("<Escape>", lambda _e: self.root.destroy())
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="设置 / 选择宠物", command=self.open_panel)
        self.menu.add_command(label="跳舞！", command=self.manual_dance)
        self.menu.add_command(label="隐藏宠物", command=self.hide_pet)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self.root.destroy)
        self.panel = None
        self.animate()
        self.root.after(900, self.idle_message)

    def popup(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def start_drag(self, event):
        self.drag = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def move_drag(self, event):
        if self.drag:
            self.root.geometry(f"+{event.x_root-self.drag[0]}+{event.y_root-self.drag[1]}")

    def pet_click(self, _event=None):
        self.clicks += 1
        responses = (ANIMALS[self.animal.get()][1], ANIMALS[self.animal.get()][2], "开心地蹭蹭你～", "继续加油呀！")
        self.say(responses[(self.clicks - 1) % len(responses)])
        self.dancing = True
        self.beat = 1.0
        self.root.after(850, lambda: setattr(self, "dancing", False) if not self.audio_on else None)

    def say(self, message, duration=1800):
        self.canvas.itemconfigure(self.bubble_id, text=message)
        self.bubble_until = time.monotonic() + duration / 1000

    def manual_dance(self):
        self.dancing = True
        self.say("音乐时间！", 1300)
        if not self.audio_on:
            self.root.after(1400, lambda: setattr(self, "dancing", False))

    def hide_pet(self):
        self.root.withdraw()
        if self.panel and self.panel.winfo_exists():
            self.panel.deiconify()

    def show_pet(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)

    def idle_message(self):
        if self.mode.get() == "陪伴" and random.random() < .2:
            self.say(ANIMALS[self.animal.get()][3], 2400)
        elif self.mode.get() == "休息" and random.random() < .12:
            self.say("记得起来活动一下哦", 2400)
        self.root.after(18000, self.idle_message)

    def make_pet_frames(self):
        """Draw a cozy anime-style chibi maid with soft hair and cloth details."""
        if Image is None:
            raise RuntimeError("需要 Pillow 绘制角色，请运行 安装依赖.bat")
        scale = 2
        im = Image.new("RGBA", (240*scale, 250*scale), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        def box(b): return tuple(int(v*scale) for v in b)
        def ellipse(b, fill, outline=None, width=1): d.ellipse(box(b), fill=fill, outline=outline, width=width*scale)
        def polygon(points, fill): d.polygon([(int(x*scale),int(y*scale)) for x,y in points], fill=fill)
        def line(points, fill, width=1): d.line([(int(x*scale),int(y*scale)) for x,y in points], fill=fill, width=width*scale, joint="curve")
        # Long navy hair behind the face, with curled tips and a warm shaded silhouette.
        ellipse((38,43,202,174),(38,46,75,255))
        polygon([(48,97),(25,161),(43,151),(36,190),(61,173),(72,126)],(47,57,91,255))
        polygon([(190,93),(218,145),(200,147),(211,177),(186,169),(173,126)],(47,57,91,255))
        ellipse((41,75,72,169),(55,69,106,255)); ellipse((168,73,199,172),(55,69,106,255))
        # Outfit: puff sleeves, navy dress, cream apron, scalloped skirt hem.
        ellipse((63,151,101,190),(250,232,225,255)); ellipse((139,151,177,190),(250,232,225,255))
        polygon([(88,158),(151,158),(180,220),(60,220)],(49,55,81,255))
        polygon([(98,162),(142,162),(162,212),(78,212)],(248,242,231,255))
        line([(101,164),(120,180),(139,164)],(226,205,195,255),2)
        ellipse((114,181,126,193),(187,132,151,255))
        for x in range(70,174,13):
            ellipse((x,211,x+15,225),(255,246,237,255))
        # Hands and tiny shoes.
        ellipse((57,170,82,190),(255,222,203,255)); ellipse((158,170,183,190),(255,222,203,255))
        ellipse((85,226,111,240),(62,59,78,255)); ellipse((129,226,155,240),(62,59,78,255))
        ellipse((89,229,105,233),(255,246,237,255)); ellipse((133,229,149,233),(255,246,237,255))
        # Face and soft cheek blush.
        ellipse((48,44,192,166),(255,226,210,255))
        # Hair cap, side locks, fringe, and individually drawn warm highlights.
        ellipse((42,32,198,127),(43,51,83,255))
        polygon([(47,71),(67,57),(83,68),(100,53),(118,68),(139,53),(161,65),(188,56),(181,102),(161,91),(147,108),(129,89),(110,108),(94,88),(75,105),(57,90)],(47,57,91,255))
        polygon([(69,61),(88,58),(83,83),(68,91)],(63,77,115,255))
        polygon([(104,55),(124,58),(112,91),(98,97)],(63,77,115,255))
        polygon([(145,57),(162,63),(145,91),(132,97)],(63,77,115,255))
        line([(72,44),(91,39),(104,42)],(139,158,190,255),2)
        line([(145,42),(160,46),(168,51)],(139,158,190,255),2)
        # Maid headband with soft scalloped lace and a side bow.
        d.arc(box((53,27,187,82)),180,360,fill=(246,239,229,255),width=5*scale)
        for x in range(63,179,10): ellipse((x,27-abs(120-x)*.08,x+8,38-abs(120-x)*.08),(255,251,242,255))
        line([(59,53),(181,53)],(240,228,216,255),2)
        polygon([(179,58),(197,48),(194,65),(207,73),(188,79),(177,70)],(151,177,202,255))
        ellipse((183,63,191,71),(213,185,196,255))
        # Huge glossy blue eyes with warm lower reflections, lashes, blush and smile.
        for x in (82,158):
            ellipse((x-17,88,x+17,127),(255,252,247,255))
            ellipse((x-12,91,x+12,124),(70,99,145,255))
            ellipse((x-9,98,x+9,123),(42,67,112,255))
            ellipse((x-7,114,x+7,122),(135,155,190,255))
            ellipse((x-8,94,x+1,103),(255,255,255,255))
            ellipse((x+4,106,x+9,112),(221,234,247,255))
            line([(x-16,94),(x-10,87),(x-3,86)],(50,50,68,255),2)
        ellipse((58,127,91,137),(246,156,158,75)); ellipse((149,127,182,137),(246,156,158,75))
        ellipse((115,128,125,136),(222,130,141,255))
        line([(116,137),(120,140),(125,137)],(135,76,87,255),1)
        # Pearl buttons and small stitched trim finish the cozy handmade look.
        for y in (190,199,208): ellipse((117,y,123,y+5),(211,173,164,255))
        d.arc(box((81,156,159,221)),0,180,fill=(255,255,255,200),width=2*scale)
        im=im.resize((240,250),Image.Resampling.LANCZOS)
        resample=getattr(Image,"Resampling",Image).BICUBIC
        angles=tuple(range(-36,37,3))
        self.pet_frames=[ImageTk.PhotoImage(im.rotate(a,resample=resample,expand=False)) for a in angles]

    def change_animal(self):
        self.make_pet_frames()
        self.canvas.itemconfigure(self.pet_id,image=self.pet_frames[len(self.pet_frames)//2])

    def animate(self):
        self.offset += 1
        self.beat *= .88
        bars = min(10, int(self.level * 10))
        if self.panel and self.panel.winfo_exists():
            self.meter.set("音量  " + "▰" * bars + "▱" * (10 - bars))
        if self.audio_on:
            self.dancing = self.level > .006
        if self.dancing:
            amp = min(1.0, self.level * 10) if self.audio_on else .6
            pulse = max(self.beat, .16 if not self.audio_on else 0)
            t = self.offset * .11
            style = self.dance_style
            if style == 1:  # bounce
                x, y, turn = math.sin(t*.5)*5, abs(math.sin(t))* (12+20*pulse+8*amp), math.sin(t*.5)*8
            elif style == 2:  # side sway
                x, y, turn = math.sin(t)* (18+10*amp), abs(math.sin(t*2))*5, math.sin(t)*24
            elif style == 3:  # spin / twirl illusion
                x, y, turn = math.sin(t*1.6)*11, abs(math.sin(t*1.6))*13, math.sin(t*1.6)*34
            elif style == 4:  # step dance
                x, y, turn = math.sin(t*1.5)*15, (7 if math.sin(t*3)>0 else 0)+pulse*11, math.sin(t*1.5)*17
            elif style == 5:  # party groove
                x, y, turn = math.sin(t*1.8)*(15+8*pulse), abs(math.sin(t*2.5))*(8+18*pulse), math.sin(t*2.2)*29
            else:
                x, y, turn = math.sin(t*2)*(9+12*amp), abs(math.sin(t*2))*(7+14*pulse), math.sin(t)*21
            self.canvas.coords(self.pet_id, 130 + x, 142 + y)
            frame = int(round((turn + 36) / 3))
            frame = max(0, min(len(self.pet_frames)-1, frame))
            self.canvas.itemconfigure(self.pet_id, image=self.pet_frames[frame])
            self.canvas.coords("shadow", 38 + abs(x), 192, 222 - abs(x), 224)
        else:
            y = math.sin(self.offset * .08) * 2
            self.canvas.coords(self.pet_id, 130, 142 + y)
            self.canvas.itemconfigure(self.pet_id, image=self.pet_frames[len(self.pet_frames)//2])
            self.canvas.coords("shadow", 38, 192, 222, 224)
        if time.monotonic() > self.bubble_until:
            self.canvas.itemconfigure(self.bubble_id, text="")
        self.root.after(45, self.animate)

    def audio_worker(self):
        try:
            if np is None:
                raise RuntimeError("缺少音频分析依赖，请运行 安装依赖.bat")
            speaker = sc.default_speaker()
            self.audio_source = speaker.name
            loopback = sc.get_microphone(speaker.name, include_loopback=True)
            while self.audio_on:
                with loopback.recorder(samplerate=16000) as recorder:
                    while self.audio_on:
                        data = recorder.record(numframes=1600)
                        mono = np.asarray(data, dtype=np.float32).mean(axis=1)
                        rms = float(np.sqrt(np.mean(mono * mono)))
                        self.level = min(1.0, rms * 12)
                        # Low-frequency energy and positive spectral flux emphasize kick/snare onsets.
                        spectrum = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
                        low = float(np.mean(spectrum[2:18])) if len(spectrum) > 18 else float(np.mean(spectrum))
                        baseline = float(np.median(self.low_history)) if self.low_history else low
                        now = time.monotonic()
                        if len(self.low_history) >= 6 and low > max(baseline * 1.48, .0008) and now - self.last_beat > .24:
                            self.beat = 1.0
                            self.last_beat = now
                        self.low_history.append(low)
                        time.sleep(.015)
        except Exception as exc:
            self.level = 0
            detail = str(exc)
            self.root.after(0, lambda: self.audio_error(detail))

    def audio_error(self, detail):
        self.audio_on = False
        if self.panel and self.panel.winfo_exists():
            self.audio_button.configure(text="▶ 开始跟随系统音乐")
            self.status.set(f"系统音频采集失败：{detail[:180]}")
        print("Audio loopback error:", detail)

    def toggle_audio(self):
        if not self.audio_on:
            if sc is None:
                self.status.set("请先安装 soundcard：运行 安装依赖.bat")
                return
            self.audio_on = True
            self.audio_button.configure(text="■ 停止音乐跟随")
            self.status.set("正在聆听电脑播放的声音…")
            threading.Thread(target=self.audio_worker, daemon=True).start()
        else:
            self.audio_on = False
            self.level = 0
            self.low_history.clear()
            self.dancing = False
            self.audio_button.configure(text="▶ 开始跟随系统音乐")
            self.status.set("已停止音乐跟随")

    def open_panel(self):
        self.show_pet()
        if self.panel and self.panel.winfo_exists():
            self.panel.deiconify()
            self.panel.lift()
            return
        p = tk.Toplevel(self.root)
        self.panel = p
        p.title("Momo · 桌面宠物")
        p.geometry("370x540")
        p.resizable(False, False)
        p.attributes("-topmost", True)
        p.configure(bg="#fff9f4")
        p.protocol("WM_DELETE_WINDOW", p.withdraw)
        style = ttk.Style(p)
        style.configure("TCombobox", padding=7)
        wrap = tk.Frame(p, bg="#fff9f4", padx=22, pady=18)
        wrap.pack(fill="both", expand=True)
        tk.Label(wrap, text="Momo 桌面宠物", bg="#fff9f4", fg="#362a3b", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        tk.Label(wrap, text="挑一位伙伴，让它陪你工作和听歌", bg="#fff9f4", fg="#827785", font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 17))
        tk.Label(wrap, text="选择动物", bg="#fff9f4", fg="#493d4e", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Combobox(wrap, textvariable=self.animal, values=list(ANIMALS), state="readonly").pack(fill="x", pady=(5, 14))
        self.animal.trace_add("write", lambda *_: self.change_animal())
        tk.Label(wrap, text="陪伴模式", bg="#fff9f4", fg="#493d4e", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Combobox(wrap, textvariable=self.mode, values=list(MODES), state="readonly").pack(fill="x", pady=(5, 4))
        tk.Label(wrap, textvariable=self.mode, bg="#fff9f4", fg="#918894", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 15))
        self.audio_button = tk.Button(wrap, text="▶ 开始跟随系统音乐", command=self.toggle_audio, bg="#7254d8", fg="white", activebackground="#6243c7", activeforeground="white", relief="flat", font=("Segoe UI", 11, "bold"), pady=11, cursor="hand2")
        self.audio_button.pack(fill="x")
        tk.Label(wrap, textvariable=self.meter, bg="#fff9f4", fg="#7254d8", font=("Consolas", 10)).pack(anchor="w", pady=(5, 0))
        tk.Button(wrap, text="♪   试听跳舞动作", command=self.manual_dance, bg="#eee8fb", fg="#604bb1", relief="flat", font=("Segoe UI", 10, "bold"), pady=9, cursor="hand2").pack(fill="x", pady=(8, 14))
        self.dance_button = tk.Button(wrap, text=f"舞步：{self.dance_styles[self.dance_style]}  ↻", command=self.next_dance, bg="#f5efff", fg="#604bb1", relief="flat", font=("Segoe UI", 9, "bold"), pady=7, cursor="hand2")
        self.dance_button.pack(fill="x", pady=(0, 12))
        tk.Label(wrap, text="互动方式", bg="#fff9f4", fg="#493d4e", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(wrap, text="点击宠物：摸摸它并触发动作\n拖动宠物：放到你喜欢的位置\n右键宠物：快捷菜单   ·   双击：打开设置", justify="left", bg="#fff9f4", fg="#827785", font=("Segoe UI", 9), pady=7).pack(anchor="w")
        tk.Label(wrap, textvariable=self.status, bg="#fff9f4", fg="#7a60c8", font=("Segoe UI", 9), wraplength=320).pack(anchor="w", pady=(8, 2))
        tk.Button(wrap, text="隐藏宠物", command=self.hide_pet, bg="#f2eeec", fg="#605963", relief="flat", pady=7).pack(fill="x", pady=(10, 0))

    def next_dance(self):
        self.dance_style = (self.dance_style + 1) % len(self.dance_styles)
        if self.panel and self.panel.winfo_exists():
            self.dance_button.configure(text=f"舞步：{self.dance_styles[self.dance_style]}  ↻")
        self.say(self.dance_styles[self.dance_style] + "！", 1300)

    def run(self):
        self.open_panel()
        self.root.mainloop()


if __name__ == "__main__":
    DesktopPet().run()

