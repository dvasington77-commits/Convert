"""
💿 CD/DVD/Game Envelope Creator Pro
Редактор конвертов для CD/DVD дисков и игр с принтами.

Возможности:
- Типоразмеры: CD slim, стандарт, mini, DVD, Digipack, кастом
- Режимы: Аудио (треклист) / Игра (жанр, платформа, издатель...)
- Drag&drop файлов из проводника
- Импорт треклиста из txt/m3u/cue
- Автозаполнение из MP3-тегов
- Пресеты-шаблоны фонов (винил, ретро, кино, неон, минимализм, игровой)
- Батч-режим для обработки папки с альбомами
- Сохранение/загрузка проектов (.cdenv)
- Экспорт PNG (300 DPI) и PDF (для печати на A4)
- Зум колёсиком, панорамирование, кэширование
"""

import tkinter as tk
from tkinter import filedialog, colorchooser, messagebox, ttk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import os
import json
import base64
import io
import time
import tempfile
from functools import lru_cache

# === Опциональные зависимости ===
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

try:
    from mutagen import File as MutagenFile
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False


# ==================== КОНСТАНТЫ ====================
MM_TO_PX = 300 / 25.4

# Пресеты типоразмеров
PRESETS = {
    "💿 CD slim 126×126": {
        "sq": 126, "flap": 20, "tab": 5, "inset": 3, "rect_h": None, "mode": "audio"
    },
    "💿 CD стандарт 130×130": {
        "sq": 130, "flap": 25, "tab": 5, "inset": 3, "rect_h": None, "mode": "audio"
    },
    "💿 CD большой 140×140": {
        "sq": 140, "flap": 28, "tab": 6, "inset": 4, "rect_h": None, "mode": "audio"
    },
    "💿 Mini CD 80×80": {
        "sq": 80, "flap": 15, "tab": 4, "inset": 2, "rect_h": None, "mode": "audio"
    },
    "📀 DVD 135×190": {
        "sq": 135, "flap": 25, "tab": 5, "inset": 3, "rect_h": 190, "mode": "audio"
    },
    "🎮 Игровой CD 130×130": {
        "sq": 130, "flap": 25, "tab": 5, "inset": 3, "rect_h": None, "mode": "game"
    },
    "🎮 Игровой DVD 135×190": {
        "sq": 135, "flap": 25, "tab": 5, "inset": 3, "rect_h": 190, "mode": "game"
    },
    "📦 Digipack 140×125": {
        "sq": 140, "flap": 25, "tab": 6, "inset": 3, "rect_h": 125, "mode": "audio"
    },
    "⚙ Кастомный": None,
}


# Текущие размеры (пересчитываются при смене пресета)
SQUARE_MM = 130
FLAP_SIZE_MM = 25
TAB_SIZE_MM = 5
TRAPEZ_INSET_MM = 3
RECT_H_MM = None

SQ = int(SQUARE_MM * MM_TO_PX)
FLAP = int(FLAP_SIZE_MM * MM_TO_PX)
TAB = int(TAB_SIZE_MM * MM_TO_PX)
INS = int(TRAPEZ_INSET_MM * MM_TO_PX)


@lru_cache(maxsize=128)
def get_font(size, bold=False):
    for name in (["arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"] if bold
                 else ["arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"]):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ==================== ГЕНЕРАТОР ШАБЛОНОВ ====================
class TemplateGenerator:
    """Генерирует фоновые шаблоны программно."""

    @staticmethod
    def vinyl(w, h, bg="#111111", accent="#ff4444"):
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)
        cx, cy = w // 2, h // 2
        step = max(3, min(w, h) // 60)
        for r in range(min(w, h) // 2, 0, -step):
            shade = int(30 + 20 * (r / (min(w, h) // 2)))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                         outline=(shade, shade, shade), width=1)
        r_label = min(w, h) // 6
        draw.ellipse([cx - r_label, cy - r_label, cx + r_label, cy + r_label],
                     fill=accent)
        r_hole = max(3, r_label // 8)
        draw.ellipse([cx - r_hole, cy - r_hole, cx + r_hole, cy + r_hole], fill=bg)
        return img

    @staticmethod
    def retro(w, h):
        img = Image.new("RGB", (w, h), "#f4e8c1")
        draw = ImageDraw.Draw(img)
        for i in range(-h, w + h, 40):
            draw.line([(i, 0), (i + h, h)], fill="#e8d4a0", width=2)
        margin = 15
        draw.rectangle([margin, margin, w - margin, h - margin],
                       outline="#8b4513", width=3)
        for (cx, cy) in [(margin, margin), (w - margin, margin),
                         (margin, h - margin), (w - margin, h - margin)]:
            draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8],
                         outline="#8b4513", width=2)
        return img

    @staticmethod
    def cinema(w, h):
        img = Image.new("RGB", (w, h), "#1a1a1a")
        draw = ImageDraw.Draw(img)
        band_h = max(20, h // 10)
        for y in [0, h - band_h]:
            draw.rectangle([0, y, w, y + band_h], fill="#000000")
            for x in range(10, w - 10, 25):
                draw.rectangle([x, y + band_h // 2 - 6,
                                x + 12, y + band_h // 2 + 6], fill="#f0f0f0")
        return img

    @staticmethod
    def neon(w, h):
        img = Image.new("RGB", (w, h), "#0a0a1a")
        draw = ImageDraw.Draw(img)
        colors = ["#ff006e", "#8338ec", "#3a86ff", "#06ffa5"]
        for i, color in enumerate(colors):
            y = h // (len(colors) + 1) * (i + 1)
            for glow in range(8, 0, -1):
                c = tuple(int(int(color[j:j + 2], 16) * (glow / 8)) for j in (1, 3, 5))
                draw.line([(20, y), (w - 20, y + int(15 * (i - 1.5)))],
                          fill=c, width=glow)
        return img

    @staticmethod
    def minimal(w, h):
        img = Image.new("RGB", (w, h), "#fafafa")
        draw = ImageDraw.Draw(img)
        draw.line([(w // 4, h // 2), (w * 3 // 4, h // 2)],
                  fill="#333333", width=3)
        return img

    @staticmethod
    def gamepad(w, h):
        img = Image.new("RGB", (w, h), "#0d0d1a")
        draw = ImageDraw.Draw(img)
        step = max(20, min(w, h) // 15)
        for x in range(0, w, step):
            draw.line([(x, 0), (x, h)], fill="#1a1a2e", width=1)
        for y in range(0, h, step):
            draw.line([(0, y), (w, y)], fill="#1a1a2e", width=1)
        for i, color in enumerate(["#ff00ff", "#00ffff"]):
            margin = 8 + i * 4
            draw.rectangle([margin, margin, w - margin, h - margin],
                           outline=color, width=2)
        return img

    @staticmethod
    def get_generator(name):
        return {
            "🎵 Винил": TemplateGenerator.vinyl,
            "📻 Ретро": TemplateGenerator.retro,
            "🎬 Кино": TemplateGenerator.cinema,
            "🌈 Неон": TemplateGenerator.neon,
            "⬜ Минимализм": TemplateGenerator.minimal,
            "🎮 Игровой": TemplateGenerator.gamepad,
        }.get(name)


# ==================== ЗОНА С КАРТИНКОЙ ====================
class ImageZone:
    """Зона шаблона с картинкой. По умолчанию картинка вписывается ЦЕЛИКОМ."""

    def __init__(self, name, x, y, w, h):
        self.name = name
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.image = None
        self.offset_x = 0
        self.offset_y = 0
        self.scale = 1.0
        self.rotation = 0
        self.fit_mode = "contain"
        self.base_scale = 1.0
        self._cache = None
        self._cache_key = None
        self._cache_bg = None

    def contains(self, px, py):
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h

    def invalidate(self):
        self._cache = None
        self._cache_key = None

    def calc_base_scale(self):
        if self.image is None:
            self.base_scale = 1.0
            return
        img = self.image
        if self.rotation in (90, 270):
            iw, ih = img.height, img.width
        else:
            iw, ih = img.width, img.height
        if self.fit_mode == "contain":
            self.base_scale = min(self.w / iw, self.h / ih)
        else:
            self.base_scale = max(self.w / iw, self.h / ih)

    def get_rendered(self, bg_color):
        key = (self.offset_x, self.offset_y, round(self.scale, 3),
               self.rotation, self.fit_mode, round(self.base_scale, 4),
               self.w, self.h)
        if (self._cache is not None and self._cache_key == key
                and self._cache_bg == bg_color):
            return self._cache

        zone = Image.new("RGB", (self.w, self.h), bg_color)
        if self.image is None:
            self._cache = zone
            self._cache_key = key
            self._cache_bg = bg_color
            return zone

        img = self.image
        if self.rotation:
            img = img.rotate(-self.rotation, expand=True, fillcolor=bg_color)

        total_scale = self.base_scale * self.scale
        new_w = max(1, int(img.width * total_scale))
        new_h = max(1, int(img.height * total_scale))

        if new_w != img.width or new_h != img.height:
            img = img.resize((new_w, new_h), Image.LANCZOS)

        px = (self.w - new_w) // 2 + self.offset_x
        py = (self.h - new_h) // 2 + self.offset_y
        zone.paste(img, (px, py))

        self._cache = zone
        self._cache_key = key
        self._cache_bg = bg_color
        return zone

    def to_dict(self):
        data = {
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "scale": self.scale,
            "rotation": self.rotation,
            "fit_mode": self.fit_mode,
            "base_scale": self.base_scale,
            "has_image": self.image is not None,
        }
        if self.image is not None:
            buf = io.BytesIO()
            self.image.save(buf, format="PNG")
            data["image_b64"] = base64.b64encode(buf.getvalue()).decode("ascii")
        return data

    def from_dict(self, data):
        self.offset_x = data.get("offset_x", 0)
        self.offset_y = data.get("offset_y", 0)
        self.scale = data.get("scale", 1.0)
        self.rotation = data.get("rotation", 0)
        self.fit_mode = data.get("fit_mode", "contain")
        self.base_scale = data.get("base_scale", 1.0)
        if data.get("has_image") and "image_b64" in data:
            raw = base64.b64decode(data["image_b64"])
            self.image = Image.open(io.BytesIO(raw)).convert("RGB")
        else:
            self.image = None
        self.invalidate()


# ==================== ГЛАВНОЕ ПРИЛОЖЕНИЕ ====================
class CDEnvelopeEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("💿 CD/DVD/Game Envelope Creator Pro")
        self.root.geometry("1500x950")
        self.root.configure(bg="#1e1e1e")

        self.bg_color = "#ffffff"
        self.line_color = "#999999"
        self.show_folds = True
        self.show_marks = True

        # Текст: общий
        self.title_text = "Название альбома"
        self.subtitle_text = "Исполнитель • 2024"

        # Аудио
        self.tracks_text = "01. Первый трек\n02. Второй трек\n03. Третий трек\n04. Четвёртый трек"

        # Игровой режим — отдельные поля
        self.game_genre = "Action / RPG"
        self.game_platform = "PC / Windows"
        self.game_year = "2024"
        self.game_developer = "Studio Name"
        self.game_publisher = "Publisher Inc."
        self.game_requirements = "OS: Windows 10+\nCPU: Intel i5\nRAM: 8 GB\nGPU: GTX 1060"
        self.game_description = "Описание игры, сюжет,\nосновные фишки и особенности.\nВведите свой текст здесь."

        self.envelope_mode = "audio"

        self.total_w = SQ + 2 * TAB
        back_h = int((RECT_H_MM if RECT_H_MM else SQUARE_MM) * MM_TO_PX)
        self.total_h = SQ + back_h + TAB

        self.zones = {
            "front": ImageZone("front", TAB, 0, SQ, SQ),
            "back":  ImageZone("back", TAB, SQ, SQ, back_h),
        }
        self.selected_zone = "front"

        self.drag_start = None
        self.drag_offset_orig = None
        self.dragging_image = False

        self.zoom = 1.0
        self.fit_zoom = 1.0
        self.total_zoom = 1.0
        self.preview_offset_x = 0
        self.preview_offset_y = 0
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.panning = False
        self.pan_start = None
        self.pan_orig = None
        self.space_held = False

        self.tk_preview = None
        self.rendered_cache = None
        self._update_pending = False
        self._last_update = 0.0
        self.MIN_UPDATE_INTERVAL = 1.0 / 30.0

        self._static_layer = None
        self._static_layer_key = None

        self.setup_ui()
        self.schedule_update(immediate=True)

    # ==================== UI ====================
    def setup_ui(self):
        # Левая панель — скроллируемая
        left_outer = tk.Frame(self.root, bg="#252525", width=360)
        left_outer.pack(side=tk.LEFT, fill=tk.Y)
        left_outer.pack_propagate(False)

        # Холст со скроллом
        canvas_scroll = tk.Canvas(left_outer, bg="#252525",
                                  highlightthickness=0, width=340)
        scrollbar = tk.Scrollbar(left_outer, orient=tk.VERTICAL,
                                 command=canvas_scroll.yview)
        canvas_scroll.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        left_panel = tk.Frame(canvas_scroll, bg="#252525")
        canvas_scroll.create_window((0, 0), window=left_panel, anchor="nw",
                                     width=340)

        def _on_frame_config(e):
            canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all"))
        left_panel.bind("<Configure>", _on_frame_config)

        # Скролл колёсиком на левой панели
        def _on_mousewheel_left(event):
            canvas_scroll.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas_scroll.bind_all("<MouseWheel>", lambda e: None)  # placeholder
        left_outer.bind("<Enter>", lambda e: canvas_scroll.bind_all(
            "<MouseWheel>", _on_mousewheel_left))
        left_outer.bind("<Leave>", lambda e: canvas_scroll.unbind_all("<MouseWheel>"))

        # Правая панель — холст
        right_panel = tk.Frame(self.root, bg="#1e1e1e")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # === ЗАГОЛОВОК ===
        header = tk.Frame(left_panel, bg="#1a1a1a")
        header.pack(fill=tk.X)
        tk.Label(header, text="💿 Envelope Creator Pro",
                 font=("Arial", 14, "bold"), bg="#1a1a1a",
                 fg="#ffffff").pack(pady=10)

        # === ПРОЕКТ ===
        proj_row = tk.Frame(left_panel, bg="#252525")
        proj_row.pack(fill=tk.X, padx=10, pady=(8, 0))
        tk.Button(proj_row, text="📂 Открыть", command=self.load_project,
                  bg="#4a90d9", fg="white", relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        tk.Button(proj_row, text="💾 Проект", command=self.save_project,
                  bg="#4a90d9", fg="white", relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        # === ТИПОРАЗМЕР ===
        tk.Label(left_panel, text="📐 Типоразмер:",
                 bg="#252525", fg="#7ac4ff",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(12, 3))

        self.preset_var = tk.StringVar(value="💿 CD стандарт 130×130")
        preset_combo = ttk.Combobox(left_panel, textvariable=self.preset_var,
                                     values=list(PRESETS.keys()),
                                     state="readonly", font=("Arial", 9))
        preset_combo.pack(fill=tk.X, padx=10)
        preset_combo.bind("<<ComboboxSelected>>",
                          lambda e: self.apply_preset(self.preset_var.get()))

        # Кастомные размеры (скрыто)
        self.custom_frame = tk.LabelFrame(left_panel, text=" ⚙ Кастом (мм) ",
                                           bg="#252525", fg="#7ac4ff",
                                           font=("Arial", 9))

        tk.Label(self.custom_frame, text="Квадрат:",
                 bg="#252525", fg="#cccccc", font=("Arial", 8)).pack(anchor="w", padx=5)
        self.custom_sq = tk.IntVar(value=130)
        tk.Scale(self.custom_frame, from_=60, to=200, orient=tk.HORIZONTAL,
                 variable=self.custom_sq, bg="#252525", fg="#ffffff",
                 troughcolor="#3a3a3a", highlightthickness=0,
                 command=lambda v: self._on_custom_change()).pack(fill=tk.X, padx=5)

        tk.Label(self.custom_frame, text="Клапан:",
                 bg="#252525", fg="#cccccc", font=("Arial", 8)).pack(anchor="w", padx=5)
        self.custom_flap = tk.IntVar(value=25)
        tk.Scale(self.custom_frame, from_=10, to=50, orient=tk.HORIZONTAL,
                 variable=self.custom_flap, bg="#252525", fg="#ffffff",
                 troughcolor="#3a3a3a", highlightthickness=0,
                 command=lambda v: self._on_custom_change()).pack(fill=tk.X, padx=5)

        tk.Label(self.custom_frame, text="Трапеции:",
                 bg="#252525", fg="#cccccc", font=("Arial", 8)).pack(anchor="w", padx=5)
        self.custom_tab = tk.IntVar(value=5)
        tk.Scale(self.custom_frame, from_=3, to=15, orient=tk.HORIZONTAL,
                 variable=self.custom_tab, bg="#252525", fg="#ffffff",
                 troughcolor="#3a3a3a", highlightthickness=0,
                 command=lambda v: self._on_custom_change()).pack(fill=tk.X, padx=5)

        tk.Label(self.custom_frame, text="Скос:",
                 bg="#252525", fg="#cccccc", font=("Arial", 8)).pack(anchor="w", padx=5)
        self.custom_ins = tk.IntVar(value=3)
        tk.Scale(self.custom_frame, from_=0, to=10, orient=tk.HORIZONTAL,
                 variable=self.custom_ins, bg="#252525", fg="#ffffff",
                 troughcolor="#3a3a3a", highlightthickness=0,
                 command=lambda v: self._on_custom_change()).pack(fill=tk.X, padx=5)

        # === РЕЖИМ ===
        tk.Label(left_panel, text="🎯 Режим конверта:",
                 bg="#252525", fg="#7ac4ff",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(12, 3))

        self.mode_var = tk.StringVar(value="audio")
        mode_frame = tk.Frame(left_panel, bg="#252525")
        mode_frame.pack(fill=tk.X, padx=10)
        tk.Radiobutton(mode_frame, text="🎵 Аудио", variable=self.mode_var,
                       value="audio", command=self.on_mode_change,
                       bg="#252525", fg="#dddddd", selectcolor="#3a3a3a",
                       activebackground="#252525",
                       activeforeground="#ffffff").pack(side=tk.LEFT)
        tk.Radiobutton(mode_frame, text="🎮 Игра", variable=self.mode_var,
                       value="game", command=self.on_mode_change,
                       bg="#252525", fg="#dddddd", selectcolor="#3a3a3a",
                       activebackground="#252525",
                       activeforeground="#ffffff").pack(side=tk.LEFT, padx=15)

        # === АКТИВНАЯ ЗОНА ===
        tk.Label(left_panel, text="🖼 Активная зона:",
                 bg="#252525", fg="#7ac4ff",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(12, 3))

        self.zone_var = tk.StringVar(value="front")
        zone_frame = tk.Frame(left_panel, bg="#252525")
        zone_frame.pack(fill=tk.X, padx=10)
        tk.Radiobutton(zone_frame, text="Лицо", variable=self.zone_var,
                       value="front", command=self.on_zone_change,
                       bg="#252525", fg="#dddddd", selectcolor="#3a3a3a",
                       activebackground="#252525",
                       activeforeground="#ffffff").pack(side=tk.LEFT)
        tk.Radiobutton(zone_frame, text="Зад", variable=self.zone_var,
                       value="back", command=self.on_zone_change,
                       bg="#252525", fg="#dddddd", selectcolor="#3a3a3a",
                       activebackground="#252525",
                       activeforeground="#ffffff").pack(side=tk.LEFT, padx=15)

        tk.Button(left_panel, text="📁 Выбрать картинку",
                  command=self.load_image_to_active,
                  bg="#4a90d9", fg="white", relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 10)).pack(fill=tk.X, padx=10, pady=(8, 3))

        # === РЕЖИМ КАРТИНКИ ===
        tk.Label(left_panel, text="🖼 Режим картинки:",
                 bg="#252525", fg="#7ac4ff",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 3))

        self.fit_mode_var = tk.StringVar(value="contain")
        tk.Radiobutton(left_panel, text="📐 Вписать целиком",
                       variable=self.fit_mode_var, value="contain",
                       command=self.on_fit_mode_change,
                       bg="#252525", fg="#dddddd", selectcolor="#3a3a3a",
                       activebackground="#252525",
                       activeforeground="#ffffff",
                       font=("Arial", 9)).pack(anchor="w", padx=10)
        tk.Radiobutton(left_panel, text="🖼 Заполнить зону",
                       variable=self.fit_mode_var, value="cover",
                       command=self.on_fit_mode_change,
                       bg="#252525", fg="#dddddd", selectcolor="#3a3a3a",
                       activebackground="#252525",
                       activeforeground="#ffffff",
                       font=("Arial", 9)).pack(anchor="w", padx=10)

        # === ШАБЛОН ФОНА ===
        tk.Label(left_panel, text="🎨 Шаблон фона:",
                 bg="#252525", fg="#7ac4ff",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 3))

        self.template_var = tk.StringVar(value="— Не использовать —")
        template_combo = ttk.Combobox(
            left_panel, textvariable=self.template_var,
            values=["— Не использовать —",
                    "🎵 Винил", "📻 Ретро", "🎬 Кино",
                    "🌈 Неон", "⬜ Минимализм", "🎮 Игровой"],
            state="readonly", font=("Arial", 9)
        )
        template_combo.pack(fill=tk.X, padx=10)
        template_combo.bind("<<ComboboxSelected>>",
                            lambda e: self.apply_template(self.template_var.get()))

        # === ПОЗИЦИЯ КАРТИНКИ ===
        tk.Label(left_panel, text="🎯 Позиция картинки:",
                 bg="#252525", fg="#7ac4ff",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 3))

        tk.Label(left_panel, text="Масштаб:", bg="#252525", fg="#cccccc",
                 font=("Arial", 9)).pack(anchor="w", padx=10)
        self.scale_var = tk.DoubleVar(value=1.0)
        tk.Scale(left_panel, from_=0.1, to=5.0, resolution=0.05,
                 orient=tk.HORIZONTAL, variable=self.scale_var,
                 command=self.on_scale_change,
                 bg="#252525", fg="#ffffff", troughcolor="#3a3a3a",
                 highlightthickness=0, length=320).pack(fill=tk.X, padx=10)

        tk.Label(left_panel, text="Смещение X:", bg="#252525", fg="#cccccc",
                 font=("Arial", 9)).pack(anchor="w", padx=10)
        self.offset_x_var = tk.IntVar(value=0)
        tk.Scale(left_panel, from_=-800, to=800, orient=tk.HORIZONTAL,
                 variable=self.offset_x_var, command=self.on_offset_change,
                 bg="#252525", fg="#ffffff", troughcolor="#3a3a3a",
                 highlightthickness=0, length=320).pack(fill=tk.X, padx=10)

        tk.Label(left_panel, text="Смещение Y:", bg="#252525", fg="#cccccc",
                 font=("Arial", 9)).pack(anchor="w", padx=10)
        self.offset_y_var = tk.IntVar(value=0)
        tk.Scale(left_panel, from_=-800, to=800, orient=tk.HORIZONTAL,
                 variable=self.offset_y_var, command=self.on_offset_change,
                 bg="#252525", fg="#ffffff", troughcolor="#3a3a3a",
                 highlightthickness=0, length=320).pack(fill=tk.X, padx=10)

        tk.Label(left_panel, text="Поворот:", bg="#252525", fg="#cccccc",
                 font=("Arial", 9)).pack(anchor="w", padx=10)
        self.rotation_var = tk.IntVar(value=0)
        tk.Scale(left_panel, from_=0, to=359, orient=tk.HORIZONTAL,
                 variable=self.rotation_var, command=self.on_rotation_change,
                 bg="#252525", fg="#ffffff", troughcolor="#3a3a3a",
                 highlightthickness=0, length=320).pack(fill=tk.X, padx=10)

        tk.Button(left_panel, text="🔄 Сбросить позицию",
                  command=self.reset_position,
                  bg="#555555", fg="white", relief=tk.FLAT,
                  cursor="hand2", font=("Arial", 9)).pack(fill=tk.X, padx=10, pady=3)

        tk.Button(left_panel, text="🗑 Убрать картинку",
                  command=self.clear_active_image,
                  bg="#a04040", fg="white", relief=tk.FLAT,
                  cursor="hand2", font=("Arial", 9)).pack(fill=tk.X, padx=10, pady=3)

        # === ОБЩИЙ ТЕКСТ ===
        tk.Label(left_panel, text="📝 Общий текст:",
                 bg="#252525", fg="#7ac4ff",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(12, 3))

        tk.Label(left_panel, text="Название:", bg="#252525", fg="#cccccc",
                 font=("Arial", 9)).pack(anchor="w", padx=10)
        self.title_entry = tk.Entry(left_panel, bg="#3a3a3a", fg="white",
                                    insertbackground="white", relief=tk.FLAT)
        self.title_entry.pack(fill=tk.X, padx=10, pady=2)
        self.title_entry.insert(0, self.title_text)
        self.title_entry.bind("<KeyRelease>", lambda e: self.on_text_change())

        tk.Label(left_panel, text="Подзаголовок:", bg="#252525", fg="#cccccc",
                 font=("Arial", 9)).pack(anchor="w", padx=10)
        self.subtitle_entry = tk.Entry(left_panel, bg="#3a3a3a", fg="white",
                                       insertbackground="white", relief=tk.FLAT)
        self.subtitle_entry.pack(fill=tk.X, padx=10, pady=2)
        self.subtitle_entry.insert(0, self.subtitle_text)
        self.subtitle_entry.bind("<KeyRelease>", lambda e: self.on_text_change())

        # === КОНТЕЙНЕРЫ ДЛЯ АУДИО / ИГРЫ ===
        self.audio_frame = tk.Frame(left_panel, bg="#252525")
        self.game_frame = tk.Frame(left_panel, bg="#252525")

        self._build_audio_fields()
        self._build_game_fields()

        # По умолчанию — аудио
        self.audio_frame.pack(fill=tk.X, padx=0, pady=0)

        # === НАСТРОЙКИ ===
        tk.Label(left_panel, text="⚙ Настройки:",
                 bg="#252525", fg="#7ac4ff",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(12, 3))

        colors_row = tk.Frame(left_panel, bg="#252525")
        colors_row.pack(fill=tk.X, padx=10)
        tk.Label(colors_row, text="Фон:", bg="#252525", fg="#cccccc").pack(side=tk.LEFT)
        self.bg_color_btn = tk.Button(colors_row, text="  ", command=self.choose_bg_color,
                                      bg=self.bg_color, width=4, relief=tk.FLAT)
        self.bg_color_btn.pack(side=tk.LEFT, padx=5)
        tk.Label(colors_row, text="Линии:", bg="#252525", fg="#cccccc").pack(side=tk.LEFT, padx=(15, 0))
        self.line_color_btn = tk.Button(colors_row, text="  ", command=self.choose_line_color,
                                        bg=self.line_color, width=4, relief=tk.FLAT)
        self.line_color_btn.pack(side=tk.LEFT, padx=5)

        self.fold_var = tk.BooleanVar(value=True)
        tk.Checkbutton(left_panel, text="Линии сгиба",
                       variable=self.fold_var, command=self.on_fold_toggle,
                       bg="#252525", fg="#cccccc", selectcolor="#3a3a3a",
                       activebackground="#252525",
                       activeforeground="#ffffff").pack(anchor="w", padx=10)

        self.marks_var = tk.BooleanVar(value=True)
        tk.Checkbutton(left_panel, text="Метки резки",
                       variable=self.marks_var, command=self.on_marks_toggle,
                       bg="#252525", fg="#cccccc", selectcolor="#3a3a3a",
                       activebackground="#252525",
                       activeforeground="#ffffff").pack(anchor="w", padx=10)

        # === ИНСТРУМЕНТЫ ===
        tk.Label(left_panel, text="🛠 Инструменты:",
                 bg="#252525", fg="#7ac4ff",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(12, 3))

        tk.Button(left_panel, text="📋 Импорт треклиста (txt/m3u/cue)",
                  command=self.import_tracklist_dialog,
                  bg="#5a5a8a", fg="white", relief=tk.FLAT,
                  cursor="hand2", font=("Arial", 9)).pack(fill=tk.X, padx=10, pady=2)

        tk.Button(left_panel, text="🎵 Заполнить из MP3-тегов",
                  command=lambda: self.autofill_from_mp3(),
                  bg="#5a5a8a", fg="white", relief=tk.FLAT,
                  cursor="hand2", font=("Arial", 9)).pack(fill=tk.X, padx=10, pady=2)

        tk.Button(left_panel, text="💾 Батч-режим (папка альбомов)",
                  command=self.batch_mode_dialog,
                  bg="#8a5a8a", fg="white", relief=tk.FLAT,
                  cursor="hand2", font=("Arial", 9)).pack(fill=tk.X, padx=10, pady=2)

        # === ЭКСПОРТ ===
        tk.Button(left_panel, text="💾 Сохранить PNG",
                  command=self.save_png,
                  bg="#3d9970", fg="white", relief=tk.FLAT,
                  cursor="hand2", font=("Arial", 10, "bold")).pack(
                      fill=tk.X, padx=10, pady=(15, 3))
        tk.Button(left_panel, text="🖨 Сохранить PDF",
                  command=self.save_pdf,
                  bg="#d97a4a", fg="white", relief=tk.FLAT,
                  cursor="hand2", font=("Arial", 10, "bold")).pack(
                      fill=tk.X, padx=10, pady=(3, 15))

        # === ХОЛСТ ===
        canvas_frame = tk.Frame(right_panel, bg="#1e1e1e")
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        top_bar = tk.Frame(canvas_frame, bg="#252525")
        top_bar.pack(fill=tk.X)
        self.canvas_title = tk.Label(top_bar, text="Шаблон развёртки",
                                      bg="#252525", fg="#ffffff",
                                      font=("Arial", 11, "bold"))
        self.canvas_title.pack(side=tk.LEFT, padx=15, pady=8)

        tk.Button(top_bar, text="➕", command=lambda: self.zoom_at_center(1.2),
                  bg="#3a3a3a", fg="white", relief=tk.FLAT, width=3,
                  cursor="hand2").pack(side=tk.RIGHT, padx=2, pady=5)
        self.zoom_label = tk.Label(top_bar, text="100%", bg="#252525",
                                   fg="#7ac4ff", font=("Arial", 9, "bold"),
                                   width=6)
        self.zoom_label.pack(side=tk.RIGHT)
        tk.Button(top_bar, text="➖", command=lambda: self.zoom_at_center(1/1.2),
                  bg="#3a3a3a", fg="white", relief=tk.FLAT, width=3,
                  cursor="hand2").pack(side=tk.RIGHT, padx=2, pady=5)
        tk.Button(top_bar, text="Fit", command=self.zoom_fit,
                  bg="#3a3a3a", fg="white", relief=tk.FLAT, width=4,
                  cursor="hand2").pack(side=tk.RIGHT, padx=2, pady=5)
        tk.Button(top_bar, text="100%", command=self.zoom_reset_100,
                  bg="#3a3a3a", fg="white", relief=tk.FLAT, width=5,
                  cursor="hand2").pack(side=tk.RIGHT, padx=2, pady=5)

        self.dnd_label = tk.Label(top_bar,
                                   text="🖱 Колёсико = зум • Ctrl+колёсико = размер",
                                   bg="#252525", fg="#7ac4ff",
                                   font=("Arial", 9))
        self.dnd_label.pack(side=tk.RIGHT, padx=15)

        self.canvas = tk.Canvas(canvas_frame, bg="#181818",
                                highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-2>", self.on_middle_click)
        self.canvas.bind("<B2-Motion>", self.on_middle_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_middle_release)

        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", self.on_mousewheel_linux)
        self.canvas.bind("<Button-5>", self.on_mousewheel_linux)

        self.root.bind("<KeyPress-space>", self.on_space_press)
        self.root.bind("<KeyRelease-space>", self.on_space_release)

        self.canvas.bind("<Configure>", lambda e: self.schedule_update(immediate=True))

        self.root.bind("<Control-s>", lambda e: self.save_project())
        self.root.bind("<Control-o>", lambda e: self.load_project())
        self.root.bind("<Control-e>", lambda e: self.save_png())

        # DnD
        if HAS_DND:
            try:
                self.canvas.drop_target_register(DND_FILES)
                self.canvas.dnd_bind('<<Drop>>', self.on_drop_files)
                self.dnd_label.config(
                    text="🖼 Кидай картинки/txt/mp3 сюда • Колёсико = зум")
            except Exception as e:
                print(f"DnD init error: {e}")

    def _build_audio_fields(self):
        """Поля для аудио-режима."""
        f = self.audio_frame

        tk.Label(f, text="📝 Аудио-режим:",
                 bg="#252525", fg="#7ac4ff",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(12, 3))

        tk.Label(f, text="Треки (по одному в строке):",
                 bg="#252525", fg="#cccccc",
                 font=("Arial", 9)).pack(anchor="w", padx=10)
        self.tracks_text_widget = tk.Text(f, height=6, bg="#3a3a3a",
                                          fg="white", insertbackground="white",
                                          relief=tk.FLAT, font=("Arial", 9))
        self.tracks_text_widget.pack(fill=tk.X, padx=10, pady=2)
        self.tracks_text_widget.insert("1.0", self.tracks_text)
        self.tracks_text_widget.bind("<KeyRelease>", lambda e: self.on_text_change())

    def _build_game_fields(self):
        """Поля для игрового режима."""
        f = self.game_frame

        tk.Label(f, text="🎮 Игровой режим:",
                 bg="#252525", fg="#ffc832",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(12, 3))

        def add_entry(label, initial, attr_name):
            tk.Label(f, text=label, bg="#252525", fg="#cccccc",
                     font=("Arial", 9)).pack(anchor="w", padx=10, pady=(5, 0))
            e = tk.Entry(f, bg="#3a3a3a", fg="white",
                         insertbackground="white", relief=tk.FLAT)
            e.pack(fill=tk.X, padx=10, pady=2)
            e.insert(0, initial)
            e.bind("<KeyRelease>", lambda ev: self.on_text_change())
            setattr(self, attr_name, e)
            return e

        add_entry("Жанр:", self.game_genre, "game_genre_entry")
        add_entry("Платформа:", self.game_platform, "game_platform_entry")
        add_entry("Год:", self.game_year, "game_year_entry")
        add_entry("Разработчик:", self.game_developer, "game_developer_entry")
        add_entry("Издатель:", self.game_publisher, "game_publisher_entry")

        tk.Label(f, text="Описание игры:", bg="#252525", fg="#cccccc",
                 font=("Arial", 9)).pack(anchor="w", padx=10, pady=(8, 0))
        self.game_description_widget = tk.Text(f, height=4, bg="#3a3a3a",
                                                fg="white", insertbackground="white",
                                                relief=tk.FLAT, font=("Arial", 9))
        self.game_description_widget.pack(fill=tk.X, padx=10, pady=2)
        self.game_description_widget.insert("1.0", self.game_description)
        self.game_description_widget.bind("<KeyRelease>",
                                           lambda e: self.on_text_change())

        tk.Label(f, text="Системные требования:", bg="#252525", fg="#cccccc",
                 font=("Arial", 9)).pack(anchor="w", padx=10, pady=(8, 0))
        self.game_requirements_widget = tk.Text(f, height=4, bg="#3a3a3a",
                                                 fg="white", insertbackground="white",
                                                 relief=tk.FLAT, font=("Arial", 9))
        self.game_requirements_widget.pack(fill=tk.X, padx=10, pady=2)
        self.game_requirements_widget.insert("1.0", self.game_requirements)
        self.game_requirements_widget.bind("<KeyRelease>",
                                            lambda e: self.on_text_change())

    # ==================== THROTTLED ОБНОВЛЕНИЕ ====================
    def schedule_update(self, immediate=False):
        if immediate:
            self._do_update()
            return
        if self._update_pending:
            return
        now = time.time()
        elapsed = now - self._last_update
        delay = max(0, int((self.MIN_UPDATE_INTERVAL - elapsed) * 1000))
        self._update_pending = True
        self.root.after(delay, self._do_update)

    def _do_update(self):
        self._update_pending = False
        self._last_update = time.time()
        self.update_preview()

    # ==================== ОБРАБОТЧИКИ UI ====================
    def on_zone_change(self):
        self.selected_zone = self.zone_var.get()
        self.sync_sliders_from_zone()
        self.schedule_update()

    def on_mode_change(self):
        self.envelope_mode = self.mode_var.get()

        # Переключаем панели
        self.audio_frame.pack_forget()
        self.game_frame.pack_forget()
        if self.envelope_mode == "audio":
            self.audio_frame.pack(fill=tk.X, padx=0, pady=0)
        else:
            self.game_frame.pack(fill=tk.X, padx=0, pady=0)

        self._static_layer = None
        self._static_layer_key = None
        self.schedule_update(immediate=True)

    def on_text_change(self):
        self.title_text = self.title_entry.get()
        self.subtitle_text = self.subtitle_entry.get()

        # Аудио
        self.tracks_text = self.tracks_text_widget.get("1.0", tk.END).strip()

        # Игра
        self.game_genre = self.game_genre_entry.get()
        self.game_platform = self.game_platform_entry.get()
        self.game_year = self.game_year_entry.get()
        self.game_developer = self.game_developer_entry.get()
        self.game_publisher = self.game_publisher_entry.get()
        self.game_description = self.game_description_widget.get("1.0", tk.END).strip()
        self.game_requirements = self.game_requirements_widget.get("1.0", tk.END).strip()

        self._static_layer = None
        self._static_layer_key = None
        self.schedule_update()

    def on_scale_change(self, _=None):
        zone = self.zones[self.selected_zone]
        zone.scale = self.scale_var.get()
        zone.invalidate()
        self.schedule_update()

    def on_offset_change(self, _=None):
        zone = self.zones[self.selected_zone]
        zone.offset_x = self.offset_x_var.get()
        zone.offset_y = self.offset_y_var.get()
        zone.invalidate()
        self.schedule_update()

    def on_rotation_change(self, _=None):
        zone = self.zones[self.selected_zone]
        zone.rotation = self.rotation_var.get()
        zone.calc_base_scale()
        zone.invalidate()
        self.schedule_update()

    def on_fit_mode_change(self):
        mode = self.fit_mode_var.get()
        zone = self.zones[self.selected_zone]
        zone.fit_mode = mode
        zone.calc_base_scale()
        zone.invalidate()
        self.schedule_update()

    def on_fold_toggle(self):
        self.show_folds = self.fold_var.get()
        self._static_layer = None
        self._static_layer_key = None
        self.schedule_update()

    def on_marks_toggle(self):
        self.show_marks = self.marks_var.get()
        self._static_layer = None
        self._static_layer_key = None
        self.schedule_update()

    def sync_sliders_from_zone(self):
        zone = self.zones[self.selected_zone]
        self.scale_var.set(zone.scale)
        self.offset_x_var.set(zone.offset_x)
        self.offset_y_var.set(zone.offset_y)
        self.rotation_var.set(zone.rotation)
        if hasattr(self, "fit_mode_var"):
            self.fit_mode_var.set(zone.fit_mode)

    def reset_position(self):
        zone = self.zones[self.selected_zone]
        zone.offset_x = 0
        zone.offset_y = 0
        zone.scale = 1.0
        zone.rotation = 0
        zone.calc_base_scale()
        zone.invalidate()
        self.sync_sliders_from_zone()
        self.schedule_update()

    def clear_active_image(self):
        self.zones[self.selected_zone].image = None
        self.zones[self.selected_zone].invalidate()
        self.schedule_update()

    def choose_bg_color(self):
        color = colorchooser.askcolor(color=self.bg_color)[1]
        if color:
            self.bg_color = color
            self.bg_color_btn.config(bg=color)
            for z in self.zones.values():
                z.invalidate()
            self._static_layer = None
            self._static_layer_key = None
            self.schedule_update()

    def choose_line_color(self):
        color = colorchooser.askcolor(color=self.line_color)[1]
        if color:
            self.line_color = color
            self.line_color_btn.config(bg=color)
            self._static_layer = None
            self._static_layer_key = None
            self.schedule_update()

    # ==================== ТИПОРАЗМЕРЫ ====================
    def apply_preset(self, preset_name):
        global SQ, TAB, INS, FLAP, RECT_H_MM
        global SQUARE_MM, TAB_SIZE_MM, TRAPEZ_INSET_MM, FLAP_SIZE_MM

        preset = PRESETS.get(preset_name)
        if preset is None:
            self.show_custom_size_controls(True)
            return

        self.show_custom_size_controls(False)

        SQUARE_MM = preset["sq"]
        FLAP_SIZE_MM = preset["flap"]
        TAB_SIZE_MM = preset["tab"]
        TRAPEZ_INSET_MM = preset["inset"]
        RECT_H_MM = preset.get("rect_h")

        SQ = int(SQUARE_MM * MM_TO_PX)
        TAB = int(TAB_SIZE_MM * MM_TO_PX)
        INS = int(TRAPEZ_INSET_MM * MM_TO_PX)
        FLAP = int(FLAP_SIZE_MM * MM_TO_PX)

        # Режим
        self.envelope_mode = preset.get("mode", "audio")
        self.mode_var.set(self.envelope_mode)
        self.on_mode_change()

        # Обновляем зоны
        back_h = int((RECT_H_MM if RECT_H_MM else SQUARE_MM) * MM_TO_PX)

        self.zones["front"].x = TAB
        self.zones["front"].y = 0
        self.zones["front"].w = SQ
        self.zones["front"].h = SQ

        self.zones["back"].x = TAB
        self.zones["back"].y = SQ
        self.zones["back"].w = SQ
        self.zones["back"].h = back_h

        self.total_w = SQ + 2 * TAB
        self.total_h = SQ + back_h + TAB

        for z in self.zones.values():
            z.calc_base_scale()
            z.invalidate()

        self._static_layer = None
        self._static_layer_key = None

        self.canvas_title.config(
            text=f"Шаблон • {SQUARE_MM:.0f}×{SQUARE_MM:.0f} мм "
                 f"({self.total_w / MM_TO_PX:.0f}×{self.total_h / MM_TO_PX:.0f} мм)")

        self.schedule_update(immediate=True)

    def apply_custom_size(self, sq_mm, flap_mm, tab_mm, inset_mm, rect_h_mm):
        global SQ, TAB, INS, FLAP, RECT_H_MM
        global SQUARE_MM, TAB_SIZE_MM, TRAPEZ_INSET_MM, FLAP_SIZE_MM

        SQUARE_MM = sq_mm
        FLAP_SIZE_MM = flap_mm
        TAB_SIZE_MM = tab_mm
        TRAPEZ_INSET_MM = inset_mm
        RECT_H_MM = rect_h_mm

        SQ = int(sq_mm * MM_TO_PX)
        TAB = int(tab_mm * MM_TO_PX)
        INS = int(inset_mm * MM_TO_PX)
        FLAP = int(flap_mm * MM_TO_PX)

        back_h = int((rect_h_mm if rect_h_mm else sq_mm) * MM_TO_PX)

        self.zones["front"].x = TAB
        self.zones["front"].y = 0
        self.zones["front"].w = SQ
        self.zones["front"].h = SQ

        self.zones["back"].x = TAB
        self.zones["back"].y = SQ
        self.zones["back"].w = SQ
        self.zones["back"].h = back_h

        self.total_w = SQ + 2 * TAB
        self.total_h = SQ + back_h + TAB

        for z in self.zones.values():
            z.calc_base_scale()
            z.invalidate()

        self._static_layer = None
        self._static_layer_key = None
        self.schedule_update(immediate=True)

    def show_custom_size_controls(self, show):
        if show:
            self.custom_frame.pack(fill=tk.X, padx=10, pady=5)
        else:
            self.custom_frame.pack_forget()

    def _on_custom_change(self):
        if self.preset_var.get() != "⚙ Кастомный":
            self.preset_var.set("⚙ Кастомный")
            self.show_custom_size_controls(True)

        self.apply_custom_size(
            self.custom_sq.get(),
            self.custom_flap.get(),
            self.custom_tab.get(),
            self.custom_ins.get(),
            None
        )

    # ==================== ШАБЛОНЫ ФОНА ====================
    def apply_template(self, name):
        if name == "— Не использовать —":
            return
        gen = TemplateGenerator.get_generator(name)
        if gen is None:
            return

        zone = self.zones[self.selected_zone]
        img = gen(zone.w, zone.h)
        zone.image = img
        zone.offset_x = 0
        zone.offset_y = 0
        zone.scale = 1.0
        zone.rotation = 0
        zone.calc_base_scale()
        zone.invalidate()
        self.sync_sliders_from_zone()
        self.schedule_update()

    # ==================== ЗАГРУЗКА КАРТИНКИ ====================
    def load_image_to_active(self):
        path = filedialog.askopenfilename(
            title=f"Картинка для зоны «{self.selected_zone}»",
            filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.gif *.webp")]
        )
        if not path:
            return
        self._load_image_into_zone(path, self.selected_zone)

    def _load_image_into_zone(self, path, zone_name):
        try:
            img = Image.open(path).convert("RGB")
            zone = self.zones[zone_name]
            zone.image = img
            zone.offset_x = 0
            zone.offset_y = 0
            zone.scale = 1.0
            zone.rotation = 0
            zone.calc_base_scale()
            zone.invalidate()
            self.sync_sliders_from_zone()
            self.schedule_update()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить:\n{e}")

    # ==================== DRAG & DROP ====================
    def on_drop_files(self, event):
        raw = event.data.strip()
        files = []
        i = 0
        while i < len(raw):
            if raw[i] == '{':
                j = raw.find('}', i)
                if j > i:
                    files.append(raw[i + 1:j])
                    i = j + 1
                else:
                    i += 1
            elif raw[i] == ' ':
                i += 1
            else:
                j = raw.find(' ', i)
                if j < 0:
                    files.append(raw[i:])
                    break
                files.append(raw[i:j])
                i = j + 1

        if not files:
            return

        first = files[0]
        ext = os.path.splitext(first)[1].lower()

        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"):
            self._load_image_into_zone(first, self.selected_zone)
        elif ext in (".txt", ".m3u", ".m3u8", ".cue", ".list"):
            self.import_tracklist_from(first)
        elif ext in (".mp3", ".flac", ".ogg", ".m4a"):
            self.autofill_from_mp3(first)
        else:
            messagebox.showinfo("Неизвестный файл",
                                 f"Формат {ext} не поддерживается для перетаскивания")

    # ==================== ИМПОРТ ТРЕКЛИСТА ====================
    def import_tracklist_dialog(self):
        path = filedialog.askopenfilename(
            title="Импорт треклиста",
            filetypes=[
                ("Текст", "*.txt"),
                ("Плейлист", "*.m3u *.m3u8"),
                ("CUE", "*.cue"),
                ("Все файлы", "*.*"),
            ]
        )
        if path:
            self.import_tracklist_from(path)

    def import_tracklist_from(self, path):
        try:
            ext = os.path.splitext(path)[1].lower()
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            tracks = []
            if ext in (".m3u", ".m3u8"):
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    name = os.path.splitext(os.path.basename(line))[0]
                    tracks.append(name)
            elif ext == ".cue":
                cur_title = None
                cur_num = None
                for line in content.splitlines():
                    line = line.strip()
                    if line.upper().startswith("TRACK"):
                        parts = line.split()
                        if len(parts) >= 2:
                            cur_num = parts[1]
                    elif line.upper().startswith("TITLE"):
                        m = line.split('"')
                        if len(m) >= 2:
                            cur_title = m[1]
                            if cur_num and cur_title:
                                tracks.append(f"{cur_num}. {cur_title}")
                            cur_title = None
                            cur_num = None
            else:
                for line in content.splitlines():
                    line = line.strip()
                    if line:
                        tracks.append(line)

            if not tracks:
                messagebox.showwarning("Пусто", "Не нашёл треков в файле")
                return

            self.tracks_text_widget.delete("1.0", tk.END)
            self.tracks_text_widget.insert("1.0", "\n".join(tracks))
            self.on_text_change()
            messagebox.showinfo("Готово", f"Импортировано треков: {len(tracks)}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось импортировать:\n{e}")

    # ==================== MP3-ТЕГИ ====================
    def autofill_from_mp3(self, path=None):
        if not HAS_MUTAGEN:
            messagebox.showerror(
                "Ошибка",
                "mutagen не установлен:\n\npython -m pip install mutagen"
            )
            return

        if path is None:
            path = filedialog.askopenfilename(
                title="Выбери MP3-файл для автозаполнения",
                filetypes=[("Аудио", "*.mp3 *.flac *.ogg *.m4a *.wav"),
                           ("Все файлы", "*.*")]
            )
            if not path:
                return

        try:
            audio = MutagenFile(path, easy=True)
            if audio is None:
                messagebox.showerror("Ошибка", "Не удалось прочитать теги")
                return

            album = (audio.get("album") or [""])[0]
            artist = (audio.get("artist") or [""])[0]
            date = (audio.get("date") or [""])[0]

            if album:
                self.title_text = album
                self.title_entry.delete(0, tk.END)
                self.title_entry.insert(0, album)

            if artist or date:
                sub = f"{artist} • {date}" if artist and date else (artist or date)
                self.subtitle_text = sub
                self.subtitle_entry.delete(0, tk.END)
                self.subtitle_entry.insert(0, sub)

            folder = os.path.dirname(path)
            audio_exts = (".mp3", ".flac", ".ogg", ".m4a", ".wav")
            files = sorted([
                f for f in os.listdir(folder)
                if os.path.splitext(f)[1].lower() in audio_exts
            ])

            tracks = []
            for fname in files:
                fpath = os.path.join(folder, fname)
                try:
                    a = MutagenFile(fpath, easy=True)
                    if a:
                        num = (a.get("tracknumber") or [""])[0]
                        t = (a.get("title") or [os.path.splitext(fname)[0]])[0]
                        num_str = num.split("/")[0].zfill(2) if num else "??"
                        tracks.append(f"{num_str}. {t}")
                    else:
                        tracks.append(os.path.splitext(fname)[0])
                except Exception:
                    tracks.append(os.path.splitext(fname)[0])

            if tracks:
                self.tracks_text = "\n".join(tracks)
                self.tracks_text_widget.delete("1.0", tk.END)
                self.tracks_text_widget.insert("1.0", self.tracks_text)

            # Автоподбор обложки
            for cover_name in ("cover.jpg", "cover.png", "folder.jpg",
                               "folder.png", "album.jpg", "album.png",
                               "front.jpg", "front.png"):
                cover_path = os.path.join(folder, cover_name)
                if os.path.isfile(cover_path):
                    self._load_image_into_zone(cover_path, "front")
                    break

            self._static_layer = None
            self._static_layer_key = None
            self.schedule_update(immediate=True)

            messagebox.showinfo(
                "Готово",
                f"Заполнено:\n"
                f"Альбом: {album or '—'}\n"
                f"Исполнитель: {artist or '—'}\n"
                f"Треков: {len(tracks)}"
            )
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать теги:\n{e}")

    # ==================== БАТЧ-РЕЖИМ ====================
    def batch_mode_dialog(self):
        folder = filedialog.askdirectory(title="Папка с альбомами (подпапки)")
        if not folder:
            return

        albums = []
        for entry in sorted(os.listdir(folder)):
            sub = os.path.join(folder, entry)
            if not os.path.isdir(sub):
                continue
            audio_exts = (".mp3", ".flac", ".ogg", ".m4a", ".wav")
            files = [f for f in os.listdir(sub)
                     if os.path.splitext(f)[1].lower() in audio_exts]
            if files:
                albums.append((entry, sub))

        if not albums:
            messagebox.showwarning("Пусто", "Не нашёл подпапок с музыкой")
            return

        out_dir = filedialog.askdirectory(title="Куда сохранять конверты?")
        if not out_dir:
            return

        fmt = messagebox.askyesnocancel(
            "Формат вывода",
            "Сохранять в PNG?\n\nДа — PNG\nНет — PDF\nОтмена — прервать"
        )
        if fmt is None:
            return

        progress = tk.Toplevel(self.root)
        progress.title("Батч-обработка...")
        progress.geometry("450x130")
        progress.configure(bg="#252525")
        tk.Label(progress, text="Обрабатываю альбомы...",
                 bg="#252525", fg="white",
                 font=("Arial", 11)).pack(pady=10)
        bar = ttk.Progressbar(progress, length=400, mode="determinate",
                              maximum=len(albums))
        bar.pack(pady=5)
        info = tk.Label(progress, text="", bg="#252525", fg="#7ac4ff",
                        font=("Arial", 9))
        info.pack()
        progress.update()

        ok = 0
        errors = []

        for i, (album_name, album_path) in enumerate(albums, 1):
            info.config(text=f"{i}/{len(albums)}: {album_name}")
            progress.update()
            bar["value"] = i

            try:
                for z in self.zones.values():
                    z.image = None
                    z.offset_x = 0
                    z.offset_y = 0
                    z.scale = 1.0
                    z.rotation = 0
                    z.invalidate()

                audio_exts = (".mp3", ".flac", ".ogg", ".m4a", ".wav")
                files = sorted([
                    f for f in os.listdir(album_path)
                    if os.path.splitext(f)[1].lower() in audio_exts
                ])

                tracks = []
                album_title = album_name
                artist = ""
                year = ""

                for fname in files:
                    fpath = os.path.join(album_path, fname)
                    try:
                        a = MutagenFile(fpath, easy=True) if HAS_MUTAGEN else None
                        if a:
                            if not artist:
                                artist = (a.get("artist") or [""])[0]
                            if not year:
                                year = (a.get("date") or [""])[0]
                            alb = (a.get("album") or [""])[0]
                            if alb and alb != album_name:
                                album_title = alb
                            num = (a.get("tracknumber") or [""])[0]
                            t = (a.get("title") or [os.path.splitext(fname)[0]])[0]
                            num_str = num.split("/")[0].zfill(2) if num else "??"
                            tracks.append(f"{num_str}. {t}")
                        else:
                            tracks.append(os.path.splitext(fname)[0])
                    except Exception:
                        tracks.append(os.path.splitext(fname)[0])

                for cover_name in ("cover.jpg", "cover.png", "folder.jpg",
                                   "folder.png", "album.jpg", "album.png",
                                   "front.jpg", "front.png"):
                    cover_path = os.path.join(album_path, cover_name)
                    if os.path.isfile(cover_path):
                        try:
                            img = Image.open(cover_path).convert("RGB")
                            z = self.zones["front"]
                            z.image = img
                            z.calc_base_scale()
                            z.invalidate()
                        except Exception:
                            pass
                        break

                self.title_text = album_title
                self.subtitle_text = (f"{artist} • {year}"
                                       if artist and year else (artist or year))
                self.tracks_text = "\n".join(tracks)
                self._static_layer = None
                self._static_layer_key = None

                out_img = self.create_envelope()
                safe_name = "".join(
                    c if c.isalnum() or c in " -_()" else "_"
                    for c in album_title
                )[:80].strip() or "album"

                if fmt:
                    out_path = os.path.join(out_dir, f"{safe_name}.png")
                    out_img.save(out_path, dpi=(300, 300))
                else:
                    out_path = os.path.join(out_dir, f"{safe_name}.pdf")
                    self._save_pdf_from_image(out_img, out_path)

                ok += 1
            except Exception as e:
                errors.append(f"{album_name}: {e}")

        progress.destroy()

        msg = f"Готово!\n\nУспешно: {ok}/{len(albums)}\nПапка: {out_dir}"
        if errors:
            msg += "\n\nОшибки:\n" + "\n".join(errors[:5])
        messagebox.showinfo("Батч завершён", msg)

    def _save_pdf_from_image(self, img, path):
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.pagesizes import A4

        tmp_dir = tempfile.gettempdir()
        tmp = os.path.join(tmp_dir,
                           f"_batch_{os.getpid()}_{int(time.time() * 1000)}.png")
        img.save(tmp, dpi=(300, 300))

        total_w_mm = SQUARE_MM + 2 * TAB_SIZE_MM
        back_h_mm = RECT_H_MM if RECT_H_MM else SQUARE_MM
        total_h_mm = SQUARE_MM + back_h_mm + TAB_SIZE_MM

        MM_TO_PT = 72 / 25.4
        page_w, page_h = A4

        c = rl_canvas.Canvas(path, pagesize=A4)
        x = (page_w - total_w_mm * MM_TO_PT) / 2
        y = (page_h - total_h_mm * MM_TO_PT) / 2
        c.drawImage(tmp, x, y,
                    width=total_w_mm * MM_TO_PT,
                    height=total_h_mm * MM_TO_PT)
        c.save()

        try:
            os.remove(tmp)
        except Exception:
            pass

    # ==================== ЗУМ И ПАНОРАМА ====================
    def on_mousewheel(self, event):
        ctrl = bool(event.state & 0x4)
        delta = 1.1 if event.delta > 0 else 1 / 1.1
        if ctrl:
            self._zoom_zone_image(delta)
        else:
            self.zoom_at_point(event.x, event.y, delta)

    def on_mousewheel_linux(self, event):
        ctrl = bool(event.state & 0x4)
        delta = 1.1 if event.num == 4 else 1 / 1.1
        if ctrl:
            self._zoom_zone_image(delta)
        else:
            self.zoom_at_point(event.x, event.y, delta)

    def _zoom_zone_image(self, factor):
        zone = self.zones[self.selected_zone]
        new_scale = max(0.1, min(5.0, zone.scale * factor))
        zone.scale = new_scale
        zone.invalidate()
        self.scale_var.set(round(new_scale, 2))
        self.schedule_update()

    def zoom_at_point(self, cx, cy, factor):
        old_zoom = self.zoom
        new_zoom = max(0.1, min(15.0, old_zoom * factor))
        if abs(new_zoom - old_zoom) < 0.001:
            return
        rel_x = cx - self.preview_offset_x
        rel_y = cy - self.preview_offset_y
        k = new_zoom / old_zoom
        self.pan_offset_x -= rel_x * (k - 1)
        self.pan_offset_y -= rel_y * (k - 1)
        self.zoom = new_zoom
        self.schedule_update()

    def zoom_at_center(self, factor):
        cw = self.canvas.winfo_width() // 2
        ch = self.canvas.winfo_height() // 2
        self.zoom_at_point(cw, ch, factor)

    def zoom_fit(self):
        self.zoom = 1.0
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.schedule_update(immediate=True)

    def zoom_reset_100(self):
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        cw = max(self.canvas.winfo_width(), 400)
        ch = max(self.canvas.winfo_height(), 400)
        ratio_w = (cw - 40) / self.total_w
        ratio_h = (ch - 40) / self.total_h
        fit = min(ratio_w, ratio_h)
        self.zoom = 1.0 / fit if fit > 0 else 1.0
        self.schedule_update(immediate=True)

    def on_space_press(self, event):
        w = self.root.focus_get()
        if isinstance(w, (tk.Entry, tk.Text)):
            return
        self.space_held = True
        self.canvas.config(cursor="fleur")

    def on_space_release(self, event):
        self.space_held = False
        self.canvas.config(cursor="crosshair")

    def on_middle_click(self, event):
        self.panning = True
        self.pan_start = (event.x, event.y)
        self.pan_orig = (self.pan_offset_x, self.pan_offset_y)
        self.canvas.config(cursor="fleur")

    def on_middle_drag(self, event):
        if not self.panning:
            return
        self.pan_offset_x = self.pan_orig[0] + (event.x - self.pan_start[0])
        self.pan_offset_y = self.pan_orig[1] + (event.y - self.pan_start[1])
        self.schedule_update()

    def on_middle_release(self, event):
        self.panning = False
        self.canvas.config(cursor="crosshair")

    # ==================== КЛИКИ ====================
    def canvas_to_envelope(self, cx, cy):
        return (cx - self.preview_offset_x) / self.total_zoom, \
               (cy - self.preview_offset_y) / self.total_zoom

    def on_canvas_click(self, event):
        ex, ey = self.canvas_to_envelope(event.x, event.y)
        for name, zone in self.zones.items():
            if zone.contains(ex, ey):
                self.selected_zone = name
                self.zone_var.set(name)
                self.sync_sliders_from_zone()
                self.dragging_image = True
                self.drag_start = (event.x, event.y)
                self.drag_offset_orig = (zone.offset_x, zone.offset_y)
                self.schedule_update()
                return
        self.dragging_image = False

    def on_canvas_drag(self, event):
        if self.space_held:
            if self.pan_start is None:
                self.pan_start = (event.x, event.y)
                self.pan_orig = (self.pan_offset_x, self.pan_offset_y)
            self.pan_offset_x = self.pan_orig[0] + (event.x - self.pan_start[0])
            self.pan_offset_y = self.pan_orig[1] + (event.y - self.pan_start[1])
            self.schedule_update()
            return

        if not self.dragging_image or self.drag_start is None:
            return
        zone = self.zones[self.selected_zone]
        dx = (event.x - self.drag_start[0]) / self.total_zoom
        dy = (event.y - self.drag_start[1]) / self.total_zoom
        zone.offset_x = int(self.drag_offset_orig[0] + dx)
        zone.offset_y = int(self.drag_offset_orig[1] + dy)
        zone.invalidate()
        self.offset_x_var.set(zone.offset_x)
        self.offset_y_var.set(zone.offset_y)
        self.schedule_update()

    def on_canvas_release(self, event):
        self.dragging_image = False
        self.drag_start = None
        self.pan_start = None

    # ==================== СТАТИЧЕСКИЙ СЛОЙ ====================
    def _build_static_layer(self):
        key = (self.bg_color, self.line_color, self.show_folds, self.show_marks,
               self.title_text, self.subtitle_text, self.tracks_text,
               self.envelope_mode, SQ, TAB, INS, RECT_H_MM,
               self.game_genre, self.game_platform, self.game_year,
               self.game_developer, self.game_publisher,
               self.game_description, self.game_requirements)

        if self._static_layer is not None and self._static_layer_key == key:
            return self._static_layer

        S = SQ
        T = TAB
        I = INS
        total_w = S + 2 * T
        back_h = int((RECT_H_MM if RECT_H_MM else SQUARE_MM) * MM_TO_PX)
        total_h = S + back_h + T

        layer = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        left = T
        right = T + S
        top_y = 0
        mid_y = S
        bot_y = S + back_h

        # ==================== ЗАДНЯЯ СТОРОНА ====================
        if self.envelope_mode == "audio":
            self._draw_audio_back(layer, draw, left, right, mid_y, back_h)
        else:
            self._draw_game_back(layer, draw, left, right, mid_y, back_h)

        # ==================== ЛИЦЕВАЯ СТОРОНА ====================
        self._draw_front(layer, draw, left, right, top_y, S)

        # ==================== ПОДПИСИ ЗОН ====================
        draw.text((left + 8, top_y + 8), "▲ ЛИЦО",
                  fill=(255, 255, 255), font=get_font(11, bold=True),
                  stroke_width=2, stroke_fill=(0, 0, 0))
        back_label = "▼ ОПИСАНИЕ" if self.envelope_mode == "game" else "▼ ТРЕКИ"
        draw.text((left + 8, mid_y + 8), back_label,
                  fill=(255, 255, 255), font=get_font(11, bold=True),
                  stroke_width=2, stroke_fill=(0, 0, 0))

        # ==================== ТРАПЕЦИИ ====================
        line_col = self.line_color if self.show_folds else None

        top_trap = [(left, top_y), (right, top_y), (right - I, 0), (left + I, 0)]
        draw.polygon(top_trap, fill=self.bg_color, outline=line_col)

        left_top_trap = [(left, top_y + I), (left, mid_y - I),
                         (0, mid_y), (0, top_y)]
        draw.polygon(left_top_trap, fill=self.bg_color, outline=line_col)

        right_top_trap = [(right, top_y + I), (right, mid_y - I),
                          (total_w, mid_y), (total_w, top_y)]
        draw.polygon(right_top_trap, fill=self.bg_color, outline=line_col)

        left_bot_trap = [(left, mid_y + I), (left, bot_y - I),
                         (0, bot_y), (0, mid_y)]
        draw.polygon(left_bot_trap, fill=self.bg_color, outline=line_col)

        right_bot_trap = [(right, mid_y + I), (right, bot_y - I),
                          (total_w, bot_y), (total_w, mid_y)]
        draw.polygon(right_bot_trap, fill=self.bg_color, outline=line_col)

        bot_trap = [(left, bot_y), (right, bot_y),
                    (right - I, bot_y + T), (left + I, bot_y + T)]
        draw.polygon(bot_trap, fill=self.bg_color, outline=line_col)

        # ==================== ЛИНИИ СГИБА ====================
        if self.show_folds:
            self._dashed_line(draw, (left, top_y), (left, mid_y), fill=self.line_color)
            self._dashed_line(draw, (right, top_y), (right, mid_y), fill=self.line_color)
            self._dashed_line(draw, (left, mid_y), (left, bot_y), fill=self.line_color)
            self._dashed_line(draw, (right, mid_y), (right, bot_y), fill=self.line_color)
            self._dashed_line(draw, (0, top_y), (total_w, top_y), fill=self.line_color)
            self._dashed_line(draw, (0, mid_y), (total_w, mid_y), fill=self.line_color)
            self._dashed_line(draw, (0, bot_y), (total_w, bot_y), fill=self.line_color)

        # ==================== РАМКА ====================
        draw.rectangle([0, 0, total_w - 1, total_h - 1],
                       outline="#333333", width=2)

        if self.show_marks:
            self._corner_marks(draw, 0, 0)
            self._corner_marks(draw, total_w - 1, 0, flip_x=True)
            self._corner_marks(draw, 0, total_h - 1, flip_y=True)
            self._corner_marks(draw, total_w - 1, total_h - 1,
                               flip_x=True, flip_y=True)

        self._static_layer = layer
        self._static_layer_key = key
        return layer

    def _draw_audio_back(self, layer, draw, left, right, mid_y, back_h):
        """Рисует заднюю сторону в аудио-режиме (треклист)."""
        S = SQ
        track_lines = [t.strip() for t in self.tracks_text.split("\n") if t.strip()]

        # Шапка
        draw.rectangle([left, mid_y, right, mid_y + 50], fill=(0, 0, 0, 170))
        draw.text((left + 12, mid_y + 12), "🎵 ТРЕКЛИСТ",
                  fill=(255, 255, 255, 255), font=get_font(20, bold=True))

        # Треки
        tracks_box_h = min(len(track_lines) * 26 + 20, back_h - 90)
        draw.rectangle([left, mid_y + 50, right, mid_y + 50 + tracks_box_h],
                       fill=(0, 0, 0, 130))

        y = mid_y + 60
        for line in track_lines:
            if y > mid_y + 50 + tracks_box_h - 20:
                break
            draw.text((left + 15, y), line, fill=(240, 240, 240, 255),
                      font=get_font(15))
            y += 26

        # Подпись
        draw.rectangle([left, mid_y + back_h - 40, right, mid_y + back_h],
                       fill=(0, 0, 0, 170))
        draw.text((left + 12, mid_y + back_h - 32),
                  f"© {self.subtitle_text or 'CD/DVD'}",
                  fill=(220, 220, 220, 255), font=get_font(12))

    def _draw_game_back(self, layer, draw, left, right, mid_y, back_h):
        """Рисует заднюю сторону в игровом режиме (описание + требования)."""
        S = SQ

        # === ШАПКА ===
        draw.rectangle([left, mid_y, right, mid_y + 55], fill=(0, 0, 0, 200))
        # Жанр и платформа в шапке
        if self.game_genre:
            draw.text((left + 12, mid_y + 8), self.game_genre.upper(),
                      fill=(255, 200, 50, 255), font=get_font(16, bold=True))
        if self.game_platform:
            draw.text((left + 12, mid_y + 32), self.game_platform,
                      fill=(200, 200, 200, 255), font=get_font(12))

        # === ОПИСАНИЕ ===
        desc_y = mid_y + 65
        desc_h = min(back_h // 2, 200)
        draw.rectangle([left + 8, desc_y, right - 8, desc_y + desc_h],
                       fill=(0, 0, 0, 130))

        y = desc_y + 10
        for line in self.game_description.split("\n"):
            if not line.strip():
                y += 8
                continue
            if y > desc_y + desc_h - 20:
                break
            draw.text((left + 18, y), line.strip(),
                      fill=(240, 240, 240, 255), font=get_font(12))
            y += 18

        # === ТРЕБОВАНИЯ ===
        req_y = desc_y + desc_h + 8
        req_h = back_h - (req_y - mid_y) - 45
        if req_h > 30:
            draw.rectangle([left + 8, req_y, right - 8, req_y + req_h],
                           fill=(0, 0, 0, 150))
            draw.text((left + 12, req_y + 5), "СИСТЕМНЫЕ ТРЕБОВАНИЯ",
                      fill=(255, 100, 100, 255), font=get_font(12, bold=True))

            y = req_y + 25
            for line in self.game_requirements.split("\n"):
                if not line.strip():
                    continue
                if y > req_y + req_h - 15:
                    break
                draw.text((left + 18, y), line.strip(),
                          fill=(220, 220, 220, 255), font=get_font(10))
                y += 14

        # === ПОДВАЛ (разработчик/издатель/год) ===
        draw.rectangle([left, mid_y + back_h - 42, right, mid_y + back_h],
                       fill=(0, 0, 0, 200))
        footer_parts = []
        if self.game_developer:
            footer_parts.append(f"👨‍💻 {self.game_developer}")
        if self.game_publisher:
            footer_parts.append(f"🏢 {self.game_publisher}")
        if self.game_year:
            footer_parts.append(f"📅 {self.game_year}")

        footer = "  •  ".join(footer_parts)
        draw.text((left + 12, mid_y + back_h - 32), footer,
                  fill=(220, 220, 220, 255), font=get_font(10))

    def _draw_front(self, layer, draw, left, right, top_y, S):
        """Рисует переднюю сторону (общее для обоих режимов)."""
        # Плашка снизу
        plashka_h = 75
        draw.rectangle([left, top_y + S - plashka_h, right, top_y + S],
                       fill=(0, 0, 0, 180))

        y = top_y + S - plashka_h + 8
        if self.title_text:
            draw.text((left + 12, y), self.title_text,
                      fill=(255, 255, 255, 255), font=get_font(20, bold=True))
            y += 28
        if self.subtitle_text:
            draw.text((left + 12, y), self.subtitle_text,
                      fill=(230, 230, 230, 255), font=get_font(14))
            y += 22

        bottom_label = "🎮 GAME DISC" if self.envelope_mode == "game" else "CD / DVD"
        draw.text((left + 12, top_y + S - 16),
                  f"{bottom_label}  •  {SQUARE_MM:.0f}×{SQUARE_MM:.0f} мм",
                  fill=(180, 180, 180, 255), font=get_font(9))

    def create_envelope(self):
        S = SQ
        T = TAB
        total_w = S + 2 * T
        back_h = int((RECT_H_MM if RECT_H_MM else SQUARE_MM) * MM_TO_PX)
        total_h = S + back_h + T

        left = T
        top_y = 0
        mid_y = S

        img = Image.new("RGB", (total_w, total_h), self.bg_color)

        back_img = self.zones["back"].get_rendered(self.bg_color)
        img.paste(back_img, (left, mid_y))
        front_img = self.zones["front"].get_rendered(self.bg_color)
        img.paste(front_img, (left, top_y))

        static = self._build_static_layer()
        img_rgba = img.convert("RGBA")
        img_rgba = Image.alpha_composite(img_rgba, static)
        img = img_rgba.convert("RGB")

        draw = ImageDraw.Draw(img)
        zone = self.zones[self.selected_zone]
        accent = "#00aaff"
        for i in range(3):
            draw.rectangle([zone.x - i, zone.y - i,
                            zone.x + zone.w + i - 1, zone.y + zone.h + i - 1],
                           outline=accent)

        return img

    def _corner_marks(self, draw, x, y, size=15, flip_x=False, flip_y=False):
        dx = -1 if flip_x else 1
        dy = -1 if flip_y else 1
        draw.line([(x, y), (x + dx * size, y)], fill="#000000", width=2)
        draw.line([(x, y), (x, y + dy * size)], fill="#000000", width=2)

    def _dashed_line(self, draw, start, end, fill="#999999", width=1, dash=6):
        x1, y1 = start
        x2, y2 = end
        if x1 == x2:
            y = min(y1, y2)
            ye = max(y1, y2)
            while y < ye:
                draw.line([(x1, y), (x2, min(y + dash, ye))], fill=fill, width=width)
                y += dash * 2
        elif y1 == y2:
            x = min(x1, x2)
            xe = max(x1, x2)
            while x < xe:
                draw.line([(x, y1), (min(x + dash, xe), y2)], fill=fill, width=width)
                x += dash * 2

    # ==================== ПРЕДПРОСМОТР ====================
    def update_preview(self):
        try:
            img = self.create_envelope()
            self.rendered_cache = img

            cw = max(self.canvas.winfo_width(), 400)
            ch = max(self.canvas.winfo_height(), 400)

            self.fit_zoom = min((cw - 40) / img.width, (ch - 40) / img.height)
            self.total_zoom = self.fit_zoom * self.zoom

            new_w = int(img.width * self.total_zoom)
            new_h = int(img.height * self.total_zoom)

            resample = Image.NEAREST if self.total_zoom >= 1.5 else Image.LANCZOS
            preview = img.resize((max(1, new_w), max(1, new_h)), resample)

            self.preview_offset_x = (cw - new_w) // 2 + self.pan_offset_x
            self.preview_offset_y = (ch - new_h) // 2 + self.pan_offset_y

            self.tk_preview = ImageTk.PhotoImage(preview)
            self.canvas.delete("all")
            self.canvas.create_image(self.preview_offset_x,
                                     self.preview_offset_y,
                                     anchor=tk.NW, image=self.tk_preview)

            if hasattr(self, "zoom_label"):
                self.zoom_label.config(text=f"{int(self.zoom * 100)}%")
        except Exception as e:
            print(f"Preview error: {e}")

    # ==================== СОХРАНЕНИЕ ПРОЕКТА ====================
    def save_project(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".cdenv",
            filetypes=[("Проект CD-конверта", "*.cdenv"), ("JSON", "*.json")],
            initialfile="my_envelope.cdenv"
        )
        if not path:
            return

        data = {
            "version": 2,
            "preset": self.preset_var.get(),
            "mode": self.envelope_mode,
            "bg_color": self.bg_color,
            "line_color": self.line_color,
            "show_folds": self.show_folds,
            "show_marks": self.show_marks,
            "title": self.title_text,
            "subtitle": self.subtitle_text,
            "tracks": self.tracks_text,
            "game": {
                "genre": self.game_genre,
                "platform": self.game_platform,
                "year": self.game_year,
                "developer": self.game_developer,
                "publisher": self.game_publisher,
                "description": self.game_description,
                "requirements": self.game_requirements,
            },
            "sizes": {
                "square_mm": SQUARE_MM,
                "flap_mm": FLAP_SIZE_MM,
                "tab_mm": TAB_SIZE_MM,
                "inset_mm": TRAPEZ_INSET_MM,
                "rect_h_mm": RECT_H_MM,
            },
            "zones": {
                "front": self.zones["front"].to_dict(),
                "back": self.zones["back"].to_dict(),
            },
        }

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Готово", f"Проект сохранён:\n{path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}")

    def load_project(self):
        path = filedialog.askopenfilename(
            title="Открыть проект",
            filetypes=[("Проект CD-конверта", "*.cdenv"),
                       ("JSON", "*.json"),
                       ("Все файлы", "*.*")]
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Типоразмер
            preset_name = data.get("preset")
            if preset_name and preset_name in PRESETS:
                self.preset_var.set(preset_name)
                self.apply_preset(preset_name)
            else:
                sizes = data.get("sizes", {})
                self.apply_custom_size(
                    sizes.get("square_mm", 130),
                    sizes.get("flap_mm", 25),
                    sizes.get("tab_mm", 5),
                    sizes.get("inset_mm", 3),
                    sizes.get("rect_h_mm")
                )

            # Режим
            self.envelope_mode = data.get("mode", "audio")
            self.mode_var.set(self.envelope_mode)

            # Цвета
            self.bg_color = data.get("bg_color", "#ffffff")
            self.line_color = data.get("line_color", "#999999")
            self.bg_color_btn.config(bg=self.bg_color)
            self.line_color_btn.config(bg=self.line_color)

            # Флаги
            self.show_folds = data.get("show_folds", True)
            self.show_marks = data.get("show_marks", True)
            self.fold_var.set(self.show_folds)
            self.marks_var.set(self.show_marks)

            # Текст
            self.title_text = data.get("title", "")
            self.subtitle_text = data.get("subtitle", "")
            self.tracks_text = data.get("tracks", "")

            self.title_entry.delete(0, tk.END)
            self.title_entry.insert(0, self.title_text)
            self.subtitle_entry.delete(0, tk.END)
            self.subtitle_entry.insert(0, self.subtitle_text)
            self.tracks_text_widget.delete("1.0", tk.END)
            self.tracks_text_widget.insert("1.0", self.tracks_text)

            # Игровые поля
            game = data.get("game", {})
            self.game_genre = game.get("genre", "")
            self.game_platform = game.get("platform", "")
            self.game_year = game.get("year", "")
            self.game_developer = game.get("developer", "")
            self.game_publisher = game.get("publisher", "")
            self.game_description = game.get("description", "")
            self.game_requirements = game.get("requirements", "")

            self.game_genre_entry.delete(0, tk.END)
            self.game_genre_entry.insert(0, self.game_genre)
            self.game_platform_entry.delete(0, tk.END)
            self.game_platform_entry.insert(0, self.game_platform)
            self.game_year_entry.delete(0, tk.END)
            self.game_year_entry.insert(0, self.game_year)
            self.game_developer_entry.delete(0, tk.END)
            self.game_developer_entry.insert(0, self.game_developer)
            self.game_publisher_entry.delete(0, tk.END)
            self.game_publisher_entry.insert(0, self.game_publisher)
            self.game_description_widget.delete("1.0", tk.END)
            self.game_description_widget.insert("1.0", self.game_description)
            self.game_requirements_widget.delete("1.0", tk.END)
            self.game_requirements_widget.insert("1.0", self.game_requirements)

            # Зоны
            zones_data = data.get("zones", {})
            for name in ("front", "back"):
                if name in zones_data:
                    self.zones[name].from_dict(zones_data[name])
                    if "base_scale" not in zones_data[name]:
                        self.zones[name].calc_base_scale()

            # Обновляем UI режима
            self.on_mode_change()

            self._static_layer = None
            self._static_layer_key = None
            for z in self.zones.values():
                z.invalidate()

            self.sync_sliders_from_zone()
            self.schedule_update(immediate=True)

            messagebox.showinfo("Готово", f"Проект загружен:\n{path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить:\n{e}")

    # ==================== ЭКСПОРТ PNG ====================
    def save_png(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
            initialfile="cd_envelope.png"
        )
        if not path:
            return

        try:
            img = self.create_envelope()
            img.save(path, dpi=(300, 300))
            if os.path.isfile(path):
                size_kb = os.path.getsize(path) / 1024
                messagebox.showinfo("Готово",
                                    f"PNG сохранён:\n{path}\n\nРазмер: {size_kb:.1f} КБ")
            else:
                messagebox.showerror("Ошибка", f"Файл не создан:\n{path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить PNG:\n{e}")

    # ==================== ЭКСПОРТ PDF ====================
    def save_pdf(self):
        try:
            from reportlab.pdfgen import canvas as rl_canvas
            from reportlab.lib.pagesizes import A4
        except ImportError as e:
            messagebox.showerror(
                "Ошибка",
                f"reportlab не установлен:\n{e}\n\n"
                f"Установи: python -m pip install reportlab"
            )
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="cd_envelope.pdf"
        )
        if not path:
            return

        path = os.path.abspath(path)
        target_dir = os.path.dirname(path)

        if not os.path.isdir(target_dir):
            messagebox.showerror("Ошибка", f"Папка не существует:\n{target_dir}")
            return

        # Тест на запись
        test_file = os.path.join(target_dir, "_test_write_.tmp")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            messagebox.showerror(
                "Ошибка",
                f"Нет прав на запись в папку:\n{target_dir}\n\n{e}"
            )
            return

        try:
            img = self.create_envelope()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось построить развёртку:\n{e}")
            return

        tmp_dir = tempfile.gettempdir()
        tmp = os.path.join(tmp_dir,
                           f"_cd_envelope_{os.getpid()}_{int(time.time() * 1000)}.png")

        try:
            img.save(tmp, dpi=(300, 300))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать временный PNG:\n{e}")
            return

        if not os.path.isfile(tmp):
            messagebox.showerror("Ошибка", f"Временный PNG не создался:\n{tmp}")
            return

        total_w_mm = SQUARE_MM + 2 * TAB_SIZE_MM
        back_h_mm = RECT_H_MM if RECT_H_MM else SQUARE_MM
        total_h_mm = SQUARE_MM + back_h_mm + TAB_SIZE_MM

        if total_h_mm > 297 or total_w_mm > 210:
            messagebox.showerror(
                "Ошибка",
                f"Развёртка {total_w_mm:.0f}×{total_h_mm:.0f} мм "
                f"не влезает на A4 (210×297 мм)!"
            )
            try:
                os.remove(tmp)
            except Exception:
                pass
            return

        MM_TO_PT = 72 / 25.4
        page_w, page_h = A4

        try:
            c = rl_canvas.Canvas(path, pagesize=A4)
            x = (page_w - total_w_mm * MM_TO_PT) / 2
            y = (page_h - total_h_mm * MM_TO_PT) / 2

            c.drawImage(tmp, x, y,
                        width=total_w_mm * MM_TO_PT,
                        height=total_h_mm * MM_TO_PT)

            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.5)
            mark = 5 * MM_TO_PT
            for (mx, my, dx, dy) in [
                (x, y, 1, 1),
                (x + total_w_mm * MM_TO_PT, y, -1, 1),
                (x, y + total_h_mm * MM_TO_PT, 1, -1),
                (x + total_w_mm * MM_TO_PT, y + total_h_mm * MM_TO_PT, -1, -1),
            ]:
                c.line(mx, my, mx + dx * mark, my)
                c.line(mx, my, mx, my + dy * mark)

            c.setFillColorRGB(0.4, 0.4, 0.4)
            c.setFont("Helvetica", 8)
            mode_label = "ИГРА" if self.envelope_mode == "game" else "АУДИО"
            c.drawString(x, y - 15,
                         f"Развёртка {total_w_mm:.0f}×{total_h_mm:.0f} мм  •  "
                         f"{mode_label}  •  квадрат {SQUARE_MM:.0f}×{SQUARE_MM:.0f} мм")

            c.showPage()
            c.save()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать PDF:\n{e}")
            try:
                os.remove(tmp)
            except Exception:
                pass
            return

        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

        if os.path.isfile(path):
            size_kb = os.path.getsize(path) / 1024
            messagebox.showinfo(
                "Готово",
                f"PDF сохранён:\n{path}\n\n"
                f"Размер файла: {size_kb:.1f} КБ\n"
                f"Развёртка: {total_w_mm:.0f}×{total_h_mm:.0f} мм"
            )
        else:
            messagebox.showerror(
                "Ошибка",
                f"reportlab отработал, но файл не создан:\n{path}"
            )


# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    app = CDEnvelopeEditor(root)

    if not HAS_DND:
        print("⚠ tkinterdnd2 не установлен — drag&drop из проводника не работает")
        print("  Установи: python -m pip install tkinterdnd2")
    if not HAS_MUTAGEN:
        print("⚠ mutagen не установлен — автозаполнение из MP3 не работает")
        print("  Установи: python -m pip install mutagen")

    root.mainloop()

