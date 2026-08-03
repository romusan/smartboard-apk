from __future__ import annotations

import ctypes
import io
import json
import threading
import time
import tkinter as tk
import urllib.request
import uuid
from ctypes import wintypes
from pathlib import Path

from PIL import Image


SERVER = "http://127.0.0.1:8000"
SESSION = "demo"
TRANSPARENT = "#010203"
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

user32.GetWindowDC.restype = wintypes.HDC
user32.GetWindowDC.argtypes = [wintypes.HWND]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
user32.PrintWindow.restype = wintypes.BOOL
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]

PW_RENDERFULLCONTENT = 2
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20
BI_RGB = 0
DIB_RGB_COLORS = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


gdi32.GetDIBits.argtypes = [
    wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
    ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
]
gdi32.GetDIBits.restype = ctypes.c_int


def presentation_window() -> tuple[int, tuple[int, int, int, int]] | None:
    matches: list[tuple[int, tuple[int, int, int, int], str]] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL

    def visit(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if not length:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        text = title.value.lower()
        if "smartboard" in text:
            return True
        supported = (
            "powerpoint" in text or "presentación con diapositivas" in text or "slide show" in text
            or ".pdf" in text or "adobe acrobat" in text or "lector de pdf" in text
        )
        if not supported:
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
        if area > 100_000:
            matches.append((hwnd, (rect.left, rect.top, rect.right, rect.bottom), text))
        return True

    user32.EnumWindows(callback_type(visit), 0)
    if not matches:
        return None
    hwnd, rect, _ = max(matches, key=lambda item: ("slide show" in item[2] or "presentación" in item[2], (item[1][2]-item[1][0])*(item[1][3]-item[1][1])))
    return hwnd, rect


def capture_window(hwnd: int, rect: tuple[int, int, int, int]) -> Image.Image | None:
    width, height = rect[2] - rect[0], rect[3] - rect[1]
    if width < 2 or height < 2:
        return None
    window_dc = user32.GetWindowDC(hwnd)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    old = gdi32.SelectObject(memory_dc, bitmap)
    try:
        if not user32.PrintWindow(hwnd, memory_dc, PW_RENDERFULLCONTENT):
            return None
        info = BITMAPINFO()
        info.bmiHeader = BITMAPINFOHEADER(
            ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, BI_RGB,
            width * height * 4, 0, 0, 0, 0,
        )
        buffer = ctypes.create_string_buffer(width * height * 4)
        gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer, ctypes.byref(info), DIB_RGB_COLORS)
        return Image.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1).copy()
    finally:
        gdi32.SelectObject(memory_dc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)


def post_json(path: str, payload: dict) -> None:
    request = urllib.request.Request(
        f"{SERVER}{path}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    urllib.request.urlopen(request, timeout=2).read()


class PowerPointOverlay:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Velo SmartBoard para PowerPoint y PDF")
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANSPARENT)
        self.root.configure(bg=TRANSPARENT)
        self.canvas = tk.Canvas(self.root, bg=TRANSPARENT, highlightthickness=0, cursor="pencil")
        self.canvas.pack(fill="both", expand=True)
        self.toolbar = tk.Toplevel(self.root)
        self.toolbar.title("SmartBoard · PowerPoint/PDF")
        self.toolbar.attributes("-topmost", True)
        self.status = tk.StringVar(value="Abre PowerPoint o un PDF para iniciar")
        self.mode_button = tk.Button(self.toolbar, text="Modo: escribir", command=self.toggle_mode, bg="#2563eb", fg="white")
        self.mode_button.pack(side="left", padx=6, pady=5)
        tk.Button(self.toolbar, text="Borrar tinta", command=self.clear, bg="#f59e0b").pack(side="left", padx=4)
        tk.Label(self.toolbar, textvariable=self.status).pack(side="left", padx=8)
        self.drawing = True
        self.points: list[tuple[float, float]] = []
        self.last_rect: tuple[int, int, int, int] | None = None
        self.canvas.bind("<Button-1>", self.start_stroke)
        self.canvas.bind("<B1-Motion>", self.extend_stroke)
        self.canvas.bind("<ButtonRelease-1>", self.end_stroke)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.running = True
        self.root.after(100, self.follow_powerpoint)
        threading.Thread(target=self.capture_loop, daemon=True).start()

    def follow_powerpoint(self) -> None:
        found = presentation_window()
        if found:
            _hwnd, rect = found
            if rect != self.last_rect:
                left, top, right, bottom = rect
                self.root.geometry(f"{right-left}x{bottom-top}+{left}+{top}")
                self.toolbar.geometry(f"+{left+12}+{top+12}")
                self.last_rect = rect
            self.status.set("Documento conectado · tableta: sesión demo")
        else:
            self.status.set("Abre PowerPoint o un PDF para iniciar")
        if self.running:
            self.root.after(350, self.follow_powerpoint)

    def capture_loop(self) -> None:
        while self.running:
            found = presentation_window()
            if found:
                image = capture_window(*found)
                if image:
                    image.thumbnail((1600, 1000), Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    image.save(output, "JPEG", quality=82, optimize=True)
                    try:
                        request = urllib.request.Request(
                            f"{SERVER}/powerpoint/frame?session_id={SESSION}", data=output.getvalue(),
                            headers={"Content-Type": "image/jpeg"}, method="POST",
                        )
                        urllib.request.urlopen(request, timeout=3).read()
                    except Exception:
                        pass
            time.sleep(0.65)

    def start_stroke(self, event: tk.Event) -> None:
        if self.drawing:
            self.points = [(event.x / max(1, self.canvas.winfo_width()), event.y / max(1, self.canvas.winfo_height()))]

    def extend_stroke(self, event: tk.Event) -> None:
        if not self.drawing or not self.points:
            return
        width, height = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        previous = self.points[-1]
        current = (event.x / width, event.y / height)
        self.canvas.create_line(previous[0]*width, previous[1]*height, event.x, event.y, fill="#ef4444", width=4, capstyle="round")
        self.points.append(current)

    def end_stroke(self, _event: tk.Event) -> None:
        if len(self.points) < 2:
            return
        now = int(time.time() * 1000)
        stroke = {
            "id": str(uuid.uuid4()), "page_id": "page-1", "color": "#ef4444", "width": 4,
            "points": [{"x": x, "y": y, "pressure": 1.0, "t": now+i} for i, (x, y) in enumerate(self.points)],
        }
        try:
            post_json(f"/overlay/stroke?session_id={SESSION}", stroke)
        except Exception:
            pass
        self.points = []

    def toggle_mode(self) -> None:
        self.drawing = not self.drawing
        style = user32.GetWindowLongW(self.root.winfo_id(), GWL_EXSTYLE)
        user32.SetWindowLongW(self.root.winfo_id(), GWL_EXSTYLE, style & ~WS_EX_TRANSPARENT if self.drawing else style | WS_EX_TRANSPARENT)
        self.mode_button.configure(text="Modo: escribir" if self.drawing else "Modo: pasar diapositivas")

    def clear(self) -> None:
        self.canvas.delete("all")

    def close(self) -> None:
        self.running = False
        self.toolbar.destroy()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    PowerPointOverlay().run()
