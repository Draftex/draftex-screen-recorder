#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Draftex Screen Recorder
=======================
Nahrávanie obrazovky (celej, jedného monitora alebo vybranej oblasti) do MP4
vrátane zvuku z ľubovoľného zvukového zariadenia registrovaného vo Windows.

Zachytí všetko, čo je na obrazovke – kontextové menu, tooltipy, popup okná,
dialógy iných aplikácií (na rozdiel od Xbox Game Bar, ktorý nahráva len jedno okno).

Požiadavky
----------
* Windows 10 / 11
* Python 3.11+ a PyQt6:      pip install PyQt6
* ffmpeg.exe v PATH alebo v priečinku so skriptom:
      winget install Gyan.FFmpeg
  (alebo "ffmpeg-release-essentials" z https://www.gyan.dev/ffmpeg/builds/)

Spustenie
---------
    pythonw screen_recorder.py          (bez konzolového okna)
    pythonw screen_recorder.py --tray   (spustí sa len do lišty, pre autoštart)

Zvuk systému ("čo počujem")
---------------------------
FFmpeg nahráva cez DirectShow, takže ponúka zariadenia, ktoré Windows eviduje
ako nahrávacie (mikrofóny, line-in, Stereo Mix, virtuálne káble...).
Na zachytenie zvuku systému zapni v Nastavenia > Zvuk > Nahrávanie zariadenie
"Stereo Mix" (ak ho ovládač ponúka), alebo nainštaluj virtuálny kábel
(napr. VB-Cable) a nastav ho ako výstup. Aplikácia vie zmiešať dve zariadenia
naraz (napr. mikrofón + Stereo Mix).

Globálna skratka: Ctrl+Shift+F9 = spustiť / zastaviť nahrávanie
(funguje aj keď je okno skryté).
"""
from __future__ import annotations

import ctypes
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (
    QAbstractNativeEventFilter,
    QDir,
    QLibraryInfo,
    QLocale,
    QLockFile,
    QObject,
    QPoint,
    QProcess,
    QRect,
    QRectF,
    QSettings,
    Qt,
    QTimer,
    QTranslator,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QRegion,
    QScreen,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "Draftex Screen Recorder"
APP_VERSION = "1.0.1"
ORG_NAME = "Draftex"
IS_WINDOWS = sys.platform == "win32"

HOTKEY_ID = 0xD7A1
WM_HOTKEY = 0x0312
HOTKEY_LABEL = "Ctrl+Shift+F9"

FPS_OPTIONS = [15, 24, 30, 60]

# kvalita -> (CRF pre libx264, bity na pixel a snímku pre HW kodéry)
QUALITY = {
    "high": (18, 0.12),
    "medium": (23, 0.08),
    "low": (28, 0.05),
}
QUALITY_LABELS = {"high": "Vysoká", "medium": "Stredná", "low": "Nízka"}
# staré hodnoty v nastaveniach (verzia 1.0.0 ukladala slovenský popisok)
QUALITY_LEGACY = {"Vysoká": "high", "Stredná": "medium", "Nízka": "low"}

ENCODER_LABELS = [
    ("libx264", "H.264 – procesor (libx264)"),
    ("h264_nvenc", "H.264 – NVIDIA (NVENC)"),
    ("h264_amf", "H.264 – AMD (AMF)"),
    ("h264_qsv", "H.264 – Intel (QSV)"),
]


# --------------------------------------------------------------------------- #
#  Jazyk – slovenčina je zdroj, angličtina cez slovník
# --------------------------------------------------------------------------- #
LANGUAGES = [("sk", "Slovenčina"), ("en", "English")]
_LANG = "sk"

TR_EN: dict[str, str] = {
    "Vysoká": "High",
    "Stredná": "Medium",
    "Nízka": "Low",
    "H.264 – procesor (libx264)": "H.264 – CPU (libx264)",
    "Ťahaním myši vyber oblasť nahrávania   •   Esc = zrušiť": "Drag with the mouse to select the recording area   •   Esc = cancel",
    "cesta k ffmpeg.exe (hľadá sa automaticky v PATH a vedľa skriptu)": "path to ffmpeg.exe (searched automatically in PATH and next to the app)",
    "Prehľadávať…": "Browse…",
    "Obraz": "Video",
    "Celá obrazovka": "Full screen",
    "Všetky monitory (celá pracovná plocha)": "All monitors (entire desktop)",
    " – hlavný": " – primary",
    "Vybraná oblasť": "Selected area",
    "Vybrať oblasť…": "Select area…",
    "žiadna oblasť nie je vybraná": "no area selected",
    "Zaznamenať kurzor myši": "Capture mouse cursor",
    "Snímková frekvencia:": "Frame rate:",
    "Kodér:": "Encoder:",
    "Kvalita:": "Quality:",
    "Zvuk": "Audio",
    "Nahrávať zvuk zo zariadenia:": "Record audio from device:",
    "Obnoviť": "Refresh",
    "Zmiešať s druhým zariadením:": "Mix with a second device:",
    "Zvuk systému („čo počujem“) sa nahrá cez zariadenie <b>Stereo Mix</b> "
    "(zapni ho v Nastavenia › Zvuk › Nahrávanie) alebo cez virtuálny kábel (VB-Cable). "
    "Mikrofón + systém zmiešaš zapnutím druhého zariadenia.":
        "System audio (“what you hear”) is recorded through the <b>Stereo Mix</b> device "
        "(enable it in Settings › Sound › Recording) or through a virtual cable (VB-Cable). "
        "Mix microphone + system audio by enabling the second device.",
    "Výstup": "Output",
    "Priečinok:": "Folder:",
    "Skryť toto okno počas nahrávania (zastavíš cez ikonu v lište alebo {hotkey})":
        "Hide this window while recording (stop via the tray icon or {hotkey})",
    "Skryť toto okno počas nahrávania (zastavíš cez ikonu v lište)":
        "Hide this window while recording (stop via the tray icon)",
    "●  Nahrávať": "●  Record",
    "■  Zastaviť": "■  Stop",
    "Otvoriť priečinok": "Open folder",
    "Pripravené.": "Ready.",
    "Zobraziť výstup FFmpeg": "Show FFmpeg output",
    "Jazyk:": "Language:",
    "Zmena jazyka sa prejaví po reštarte aplikácie. Reštartovať teraz?":
        "The language change takes effect after restarting the application. Restart now?",
    "Nahrávať": "Record",
    "Zastaviť nahrávanie": "Stop recording",
    "Zobraziť okno": "Show window",
    "Ukončiť": "Quit",
    "FFmpeg sa nenašiel – nainštaluj ho (winget install Gyan.FFmpeg) alebo zadaj cestu.":
        "FFmpeg not found – install it (winget install Gyan.FFmpeg) or enter its path.",
    "(žiadne zvukové zariadenie sa nenašlo)": "(no audio device found)",
    "Vyber ffmpeg": "Select ffmpeg",
    "Všetky súbory (*)": "All files (*)",
    "Priečinok pre nahrávky": "Folder for recordings",
    "Najprv vyber oblasť nahrávania.": "Select the recording area first.",
    "FFmpeg sa nenašiel. Nainštaluj ho alebo zadaj cestu k ffmpeg.exe.":
        "FFmpeg not found. Install it or enter the path to ffmpeg.exe.",
    "Nie je vybrané žiadne zvukové zariadenie. Vypni zvuk alebo obnov zoznam zariadení.":
        "No audio device selected. Disable audio or refresh the device list.",
    "Priečinok sa nedá vytvoriť:\n{exc}": "The folder cannot be created:\n{exc}",
    "Spúšťa sa…": "Starting…",
    "Ukončuje sa nahrávanie…": "Stopping recording…",
    "Nahrávanie zrušené.": "Recording cancelled.",
    "FFmpeg neskončil včas – vynútené ukončenie.": "FFmpeg did not finish in time – forced termination.",
    "Nahrávanie beží. Zastavíš ho cez {hotkey} alebo ikonu v lište.":
        "Recording is running. Stop it with {hotkey} or the tray icon.",
    "FFmpeg sa nepodarilo spustiť: ": "FFmpeg failed to start: ",
    "Uložené: {name} ({size})": "Saved: {name} ({size})",
    "Nahrávka uložená:\n{path}": "Recording saved:\n{path}",
    "FFmpeg skončil s chybou (kód {code}).": "FFmpeg exited with an error (code {code}).",
    "Nahrávanie zlyhalo. Posledné riadky výstupu FFmpeg:\n\n": "Recording failed. Last lines of FFmpeg output:\n\n",
    "● Nahráva sa": "● Recording",
    "Nahrávanie stále beží. Zastaviť ho a ukončiť aplikáciu?": "Recording is still running. Stop it and quit the application?",
    "Aplikácia už beží – nájdeš ju ako ikonu v lište vedľa hodín.": "The application is already running – find its icon in the tray next to the clock.",
    "Beží na pozadí. Nahrávanie: {hotkey} alebo dvojklik na ikonu.": "Running in the background. Record: {hotkey} or double-click the icon.",
}


def tr(text: str) -> str:
    """Preklad používateľského textu podľa aktuálneho jazyka (zdroj = slovenčina)."""
    if _LANG == "en":
        return TR_EN.get(text, text)
    return text


def set_language(lang: str) -> None:
    global _LANG
    _LANG = lang if lang in dict(LANGUAGES) else "sk"


def detect_language(settings: QSettings) -> str:
    """Jazyk z nastavení (zapíše ho aj inštalátor), inak podľa jazyka Windows."""
    value = str(settings.value("language", "", str) or "").strip().lower()
    if value in dict(LANGUAGES):
        return value
    return "sk" if QLocale.system().name().lower().startswith("sk") else "en"


# --------------------------------------------------------------------------- #
#  Dátové triedy
# --------------------------------------------------------------------------- #
@dataclass
class AudioDevice:
    name: str
    alt_name: str = ""

    @property
    def dshow_id(self) -> str:
        # alternatívny názov je jednoznačný aj pri dvoch rovnako pomenovaných zariadeniach
        return self.alt_name or self.name


@dataclass
class Monitor:
    name: str
    left: int
    top: int
    width: int
    height: int
    primary: bool = False

    @property
    def rect(self) -> QRect:
        return QRect(self.left, self.top, self.width, self.height)


# --------------------------------------------------------------------------- #
#  FFmpeg – vyhľadanie, zoznamy zariadení a kodérov
# --------------------------------------------------------------------------- #
def _no_window_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0


def run_ffmpeg_text(ffmpeg: str, args: list[str], timeout: float = 15) -> str:
    """Spustí ffmpeg s parametrami a vráti stdout+stderr ako text."""
    try:
        r = subprocess.run(
            [ffmpeg, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=_no_window_flags(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (r.stdout or "") + "\n" + (r.stderr or "")


def find_ffmpeg(preferred: str = "") -> str:
    exe = "ffmpeg.exe" if IS_WINDOWS else "ffmpeg"
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent
    candidates = [
        preferred,
        str(base / exe),
        str(base / "ffmpeg" / exe),
        str(base / "ffmpeg" / "bin" / exe),
        shutil.which("ffmpeg") or "",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return str(Path(c))
    return ""


def list_video_encoders(ffmpeg: str) -> list[tuple[str, str]]:
    out = run_ffmpeg_text(ffmpeg, ["-hide_banner", "-encoders"])
    available = set(re.findall(r"^\s*V\S{5}\s+(\S+)", out, re.M))
    result = [(name, label) for name, label in ENCODER_LABELS if name in available]
    return result or [ENCODER_LABELS[0]]


def list_dshow_audio_devices(ffmpeg: str) -> list[AudioDevice]:
    """Zoznam zvukových zariadení DirectShow (rozumie starému aj novému formátu výpisu)."""
    out = run_ffmpeg_text(ffmpeg, ["-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"])
    devices: list[AudioDevice] = []
    section = ""
    last: AudioDevice | None = None

    for raw in out.splitlines():
        line = raw.strip()
        if line.startswith("[dshow"):
            line = line.split("]", 1)[1].strip() if "]" in line else line

        if "DirectShow audio devices" in line:
            section = "audio"
            continue
        if "DirectShow video devices" in line:
            section = "video"
            continue

        m = re.match(r'Alternative name\s+"(.+)"\s*$', line)
        if m:
            if last is not None:
                last.alt_name = m.group(1)
            continue

        # nový formát:  "Názov" (audio)   /   "Názov" (video)   /   "Názov" (none)
        m = re.match(r'"(.+)"\s+\(([^)]*)\)\s*$', line)
        if m:
            last = None
            if "audio" in m.group(2):
                last = AudioDevice(m.group(1))
                devices.append(last)
            continue

        # starý formát:  "Názov"   (typ určuje predchádzajúca hlavička)
        m = re.match(r'^"(.+)"$', line)
        if m:
            last = None
            if section == "audio":
                last = AudioDevice(m.group(1))
                devices.append(last)
            continue

    return devices


def build_ffmpeg_args(
    *,
    fps: int,
    region: QRect | None,
    cursor: bool,
    encoder: str,
    quality: str,
    audio: list[AudioDevice],
    output: str,
    est_size: tuple[int, int],
) -> list[str]:
    """Zostaví parametre pre ffmpeg (bez názvu programu)."""
    args = ["-hide_banner", "-y", "-loglevel", "info", "-nostats"]

    # --- obraz: GDI zachytenie celej plochy / oblasti (vidí menu, popupy, kurzor)
    args += [
        "-thread_queue_size", "1024",
        "-f", "gdigrab",
        "-framerate", str(fps),
        "-draw_mouse", "1" if cursor else "0",
    ]
    if region is not None:
        args += [
            "-offset_x", str(region.x()),
            "-offset_y", str(region.y()),
            "-video_size", f"{region.width()}x{region.height()}",
        ]
    args += ["-i", "desktop"]

    # --- zvuk: DirectShow zariadenia z Windows
    for dev in audio:
        args += [
            "-thread_queue_size", "1024",
            "-rtbufsize", "256M",
            "-audio_buffer_size", "50",
            "-f", "dshow",
            "-i", f"audio={dev.dshow_id}",
        ]

    # --- filtre: párne rozmery (H.264 to vyžaduje) + yuv420p, prípadne mix zvuku
    graph = ["[0:v]crop=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p[v]"]
    if len(audio) >= 2:
        inputs = "".join(f"[{i + 1}:a]" for i in range(len(audio)))
        graph.append(
            f"{inputs}amix=inputs={len(audio)}:duration=longest:dropout_transition=0:normalize=0[a]"
        )
    args += ["-filter_complex", ";".join(graph), "-map", "[v]"]
    if len(audio) == 1:
        args += ["-map", "1:a"]
    elif len(audio) >= 2:
        args += ["-map", "[a]"]

    # --- kodér
    crf, bpp = QUALITY.get(quality, QUALITY["medium"])
    if encoder == "libx264":
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf)]
    else:
        w, h = est_size
        kbps = max(2000, int(w * h * fps * bpp / 1000))
        args += [
            "-c:v", encoder,
            "-b:v", f"{kbps}k",
            "-maxrate", f"{int(kbps * 1.5)}k",
            "-bufsize", f"{kbps * 2}k",
        ]
    args += ["-r", str(fps)]

    if audio:
        args += ["-c:a", "aac", "-b:a", "160k"]

    args += [output]
    return args


# --------------------------------------------------------------------------- #
#  Win32 – monitory (fyzické pixely, nezávisle od DPI škálovania)
# --------------------------------------------------------------------------- #
def list_monitors() -> list[Monitor]:
    if not IS_WINDOWS:
        return [Monitor("DISPLAY1", 0, 0, 1920, 1080, True)]

    from ctypes import wintypes

    user32 = ctypes.windll.user32

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]

    MonitorEnumProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
    )
    monitors: list[Monitor] = []

    def callback(hmon, _hdc, _lprc, _lparam):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            r = info.rcMonitor
            monitors.append(
                Monitor(
                    name=info.szDevice.replace("\\\\.\\", ""),
                    left=r.left,
                    top=r.top,
                    width=r.right - r.left,
                    height=r.bottom - r.top,
                    primary=bool(info.dwFlags & 1),
                )
            )
        return True

    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), MonitorEnumProc, wintypes.LPARAM]
    user32.EnumDisplayMonitors.restype = wintypes.BOOL
    user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)
    monitors.sort(key=lambda m: (not m.primary, m.left, m.top))
    return monitors or [Monitor("DISPLAY1", 0, 0, 1920, 1080, True)]


def window_rect_for_hwnd(hwnd: int) -> tuple[int, int, int, int] | None:
    """Fyzický obdĺžnik okna na obrazovke (left, top, right, bottom) – proces je DPI-aware."""
    if not IS_WINDOWS:
        return None
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    r = wintypes.RECT()
    if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(r)):
        return None
    return r.left, r.top, r.right, r.bottom


# --------------------------------------------------------------------------- #
#  Globálna klávesová skratka (Win32 RegisterHotKey + Qt native event filter)
# --------------------------------------------------------------------------- #
class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type, message):
        try:
            if bytes(event_type) == b"windows_generic_MSG":
                from ctypes import wintypes

                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    self._callback()
        except Exception:
            pass
        return False, 0


def register_global_hotkey() -> bool:
    if not IS_WINDOWS:
        return False
    MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT, VK_F9 = 0x0002, 0x0004, 0x4000, 0x78
    try:
        return bool(ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_F9))
    except Exception:
        return False


def unregister_global_hotkey() -> None:
    if IS_WINDOWS:
        try:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        except Exception:
            pass


# --------------------------------------------------------------------------- #
#  Výber oblasti – priesvitné okno cez každý monitor
# --------------------------------------------------------------------------- #
class RegionOverlay(QWidget):
    selected = pyqtSignal(QRect)   # fyzické pixely, absolútne súradnice
    cancelled = pyqtSignal()

    def __init__(self, screen: QScreen):
        super().__init__(
            None,
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self._screen = screen
        self._origin: QPoint | None = None
        self._current: QPoint | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())

    # ---- geometria
    def _selection(self) -> QRect | None:
        if self._origin is None or self._current is None:
            return None
        return QRect(self._origin, self._current).normalized().intersected(self.rect())

    def to_physical(self, r: QRect) -> QRect:
        dpr = float(self._screen.devicePixelRatio())
        mon = window_rect_for_hwnd(int(self.winId()))
        if mon is not None:
            ox, oy = mon[0], mon[1]
        else:
            g = self._screen.geometry()
            ox, oy = round(g.x() * dpr), round(g.y() * dpr)
        x = ox + round(r.x() * dpr)
        y = oy + round(r.y() * dpr)
        w = round(r.width() * dpr)
        h = round(r.height() * dpr)
        w -= w % 2
        h -= h % 2
        return QRect(x, y, w, h)

    # ---- kreslenie
    def paintEvent(self, _event: QPaintEvent) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 110))
        sel = self._selection()
        if sel is not None and sel.width() > 0 and sel.height() > 0:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            p.fillRect(sel, Qt.GlobalColor.transparent)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(QColor("#FF5252"))
            pen.setWidth(2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(sel.adjusted(0, 0, -1, -1))

            phys = self.to_physical(sel)
            label = f"{phys.width()} × {phys.height()} px"
            self._draw_label(p, label, sel.bottomRight() + QPoint(-8, -8), align_right=True)
        else:
            self._draw_label(
                p,
                tr("Ťahaním myši vyber oblasť nahrávania   •   Esc = zrušiť"),
                self.rect().center(),
                centered=True,
            )
        p.end()

    def _draw_label(self, p: QPainter, text: str, pos: QPoint, *, align_right=False, centered=False) -> None:
        font = QFont()
        font.setPointSize(11)
        p.setFont(font)
        metrics = p.fontMetrics()
        w = metrics.horizontalAdvance(text) + 20
        h = metrics.height() + 12
        if centered:
            box = QRect(pos.x() - w // 2, pos.y() - h // 2, w, h)
        elif align_right:
            box = QRect(pos.x() - w, pos.y() - h, w, h)
        else:
            box = QRect(pos.x(), pos.y(), w, h)
        box = box.intersected(self.rect()) if not centered else box
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 20, 20, 210))
        p.drawRoundedRect(box, 6, 6)
        p.setPen(QColor("white"))
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    # ---- vstup
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._origin = e.position().toPoint()
            self._current = self._origin
            self.update()
        elif e.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._origin is not None:
            self._current = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return
        self._current = e.position().toPoint()
        sel = self._selection()
        self._origin = self._current = None
        if sel is not None and sel.width() >= 8 and sel.height() >= 8:
            self.selected.emit(self.to_physical(sel))
        else:
            self.cancelled.emit()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()


class RegionSelector(QObject):
    """Otvorí overlay na všetkých monitoroch a vráti vybranú oblasť (alebo None)."""

    finished = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._overlays: list[RegionOverlay] = []
        self._done = False

    def start(self) -> None:
        self._done = False
        self._overlays = []
        for screen in QApplication.screens():
            ov = RegionOverlay(screen)
            ov.selected.connect(self._finish)
            ov.cancelled.connect(lambda: self._finish(None))
            self._overlays.append(ov)
        for ov in self._overlays:
            ov.show()
            ov.setGeometry(ov.screen().geometry())
        if self._overlays:
            self._overlays[0].activateWindow()
            self._overlays[0].setFocus()

    def _finish(self, rect) -> None:
        if self._done:
            return
        self._done = True
        for ov in self._overlays:
            ov.close()
            ov.deleteLater()
        self._overlays = []
        self.finished.emit(rect)


# --------------------------------------------------------------------------- #
#  Rám vybranej oblasti – trvalo viditeľný, priepustný pre myš
# --------------------------------------------------------------------------- #
class RegionFrame(QWidget):
    """Priesvitné okno cez celý monitor; kreslí rám okolo vybranej oblasti
    a umožňuje ťahaním za hranu / roh meniť jej rozmer.

    Rám je nakreslený TESNE MIMO oblasti (s 1 px medzerou), takže gdigrab ho
    do videa nezachytí – vo videu je presne to, čo je vnútri rámu.
    Maska okna pokrýva len úzky pás okolo hrán: kliky mimo pásu prechádzajú
    do aplikácií pod rámom, kliky na pás chytia hranu. Okno neberie fokus.
    Počas nahrávania je rám zamknutý (úplne priepustný pre vstup).
    """

    regionChanged = pyqtSignal(QRect)   # fyzické pixely, absolútne súradnice

    GAP = 1            # medzera medzi hranou oblasti a rámom (logické px)
    RED_WIDTH = 2
    WHITE_WIDTH = 1
    GRIP_OUT = 8       # pás na chytenie hrany – zvonka
    GRIP_IN = 4        # ... a zvnútra
    MIN_SIZE = 32      # minimálny rozmer oblasti (fyzické px)

    def __init__(self, screen: QScreen):
        super().__init__(
            None,
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self._screen = screen
        self._region: QRect | None = None
        self._locked = False
        self._drag_edges: tuple[bool, bool, bool, bool] | None = None   # (left, top, right, bottom)
        self._drag_start_pos: QPoint | None = None
        self._drag_start_region: QRect | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())

    # ---- verejné API
    def set_region(self, region: QRect | None) -> None:
        self._region = region
        if self.isVisible():
            self._apply_mask()
        self.update()

    def set_locked(self, locked: bool) -> None:
        """Zamknúť počas nahrávania: rám je vidieť, ale nedá sa chytiť."""
        if locked == self._locked:
            return
        self._locked = locked
        self._drag_edges = None
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, locked)
        if was_visible:
            self.show()
            self.setGeometry(self._screen.geometry())

    # ---- geometria
    def _to_logical(self, r: QRect) -> QRectF:
        """Fyzické absolútne súradnice → logické súradnice tohto okna (inverz RegionOverlay.to_physical)."""
        dpr = float(self._screen.devicePixelRatio())
        mon = window_rect_for_hwnd(int(self.winId()))
        if mon is not None:
            ox, oy = mon[0], mon[1]
        else:
            g = self._screen.geometry()
            ox, oy = round(g.x() * dpr), round(g.y() * dpr)
        return QRectF((r.x() - ox) / dpr, (r.y() - oy) / dpr, r.width() / dpr, r.height() / dpr)

    def _apply_mask(self) -> None:
        if self._region is None:
            self.setMask(QRegion(0, 0, 1, 1))
            return
        r = self._to_logical(self._region).toAlignedRect()
        outer = r.adjusted(-self.GRIP_OUT, -self.GRIP_OUT, self.GRIP_OUT, self.GRIP_OUT)
        inner = r.adjusted(self.GRIP_IN, self.GRIP_IN, -self.GRIP_IN, -self.GRIP_IN)
        region = QRegion(outer.intersected(self.rect()))
        if inner.isValid():
            region = region.subtracted(QRegion(inner))
        self.setMask(region)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_mask)   # až keď má okno finálnu polohu

    def _hit_edges(self, pos: QPoint) -> tuple[bool, bool, bool, bool] | None:
        if self._region is None:
            return None
        r = self._to_logical(self._region).toAlignedRect()
        x, y = pos.x(), pos.y()
        in_x = r.left() - self.GRIP_OUT <= x <= r.right() + self.GRIP_OUT
        in_y = r.top() - self.GRIP_OUT <= y <= r.bottom() + self.GRIP_OUT
        if not (in_x and in_y):
            return None
        left = abs(x - r.left()) <= self.GRIP_OUT and x <= r.left() + self.GRIP_IN
        right = abs(x - r.right()) <= self.GRIP_OUT and x >= r.right() - self.GRIP_IN
        top = abs(y - r.top()) <= self.GRIP_OUT and y <= r.top() + self.GRIP_IN
        bottom = abs(y - r.bottom()) <= self.GRIP_OUT and y >= r.bottom() - self.GRIP_IN
        if not (left or right or top or bottom):
            return None
        return left, top, right, bottom

    @staticmethod
    def _cursor_for(edges: tuple[bool, bool, bool, bool] | None) -> Qt.CursorShape:
        if edges is None:
            return Qt.CursorShape.ArrowCursor
        left, top, right, bottom = edges
        if (left and top) or (right and bottom):
            return Qt.CursorShape.SizeFDiagCursor
        if (left and bottom) or (right and top):
            return Qt.CursorShape.SizeBDiagCursor
        if left or right:
            return Qt.CursorShape.SizeHorCursor
        return Qt.CursorShape.SizeVerCursor

    def _dragged_region(self, pos: QPoint) -> QRect:
        assert self._drag_edges and self._drag_start_pos is not None and self._drag_start_region is not None
        dpr = float(self._screen.devicePixelRatio())
        dx = round((pos.x() - self._drag_start_pos.x()) * dpr)
        dy = round((pos.y() - self._drag_start_pos.y()) * dpr)
        left, top, right, bottom = self._drag_edges
        r = self._drag_start_region
        x1, y1 = r.x(), r.y()
        x2, y2 = r.x() + r.width(), r.y() + r.height()   # exkluzívne hrany
        if left:
            x1 = min(x1 + dx, x2 - self.MIN_SIZE)
        if right:
            x2 = max(x2 + dx, x1 + self.MIN_SIZE)
        if top:
            y1 = min(y1 + dy, y2 - self.MIN_SIZE)
        if bottom:
            y2 = max(y2 + dy, y1 + self.MIN_SIZE)
        # párne rozmery (libx264 / yuv420p) – upraví sa ťahaná hrana
        if (x2 - x1) % 2:
            if left:
                x1 += 1
            else:
                x2 -= 1
        if (y2 - y1) % 2:
            if top:
                y1 += 1
            else:
                y2 -= 1
        return QRect(x1, y1, x2 - x1, y2 - y1)

    # ---- myš
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if self._locked or e.button() != Qt.MouseButton.LeftButton:
            return
        edges = self._hit_edges(e.position().toPoint())
        if edges is None or self._region is None:
            return
        self._drag_edges = edges
        self._drag_start_pos = e.position().toPoint()
        self._drag_start_region = QRect(self._region)
        self.setCursor(self._cursor_for(edges))
        e.accept()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag_edges is not None:
            self._region = self._dragged_region(e.position().toPoint())
            self._apply_mask()
            self.update()
            self.regionChanged.emit(QRect(self._region))
            e.accept()
            return
        if not self._locked:
            self.setCursor(self._cursor_for(self._hit_edges(e.position().toPoint())))

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if self._drag_edges is None or e.button() != Qt.MouseButton.LeftButton:
            return
        self._region = self._dragged_region(e.position().toPoint())
        self._drag_edges = None
        self._apply_mask()
        self.update()
        self.regionChanged.emit(QRect(self._region))
        self.setCursor(self._cursor_for(self._hit_edges(e.position().toPoint())))
        e.accept()

    # ---- kreslenie
    def paintEvent(self, _event: QPaintEvent) -> None:
        if self._region is None:
            return
        rect = self._to_logical(self._region)
        if not rect.intersects(QRectF(self.rect())):
            return   # oblasť je na inom monitore
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # červený rám: pásik [GAP, GAP+RED_WIDTH] mimo oblasti
        d = self.GAP + self.RED_WIDTH / 2
        pen = QPen(QColor("#FF5252"))
        pen.setWidthF(self.RED_WIDTH)
        p.setPen(pen)
        p.drawRect(rect.adjusted(-d, -d, d, d))
        # biely obrys zvonka pre kontrast na tmavom pozadí
        d = self.GAP + self.RED_WIDTH + self.WHITE_WIDTH / 2
        pen = QPen(QColor(255, 255, 255, 200))
        pen.setWidthF(self.WHITE_WIDTH)
        p.setPen(pen)
        p.drawRect(rect.adjusted(-d, -d, d, d))
        # počas ťahania rozmer v rohu oblasti (nahrávanie vtedy nebeží, do videa sa nedostane)
        if self._drag_edges is not None:
            label = f"{self._region.width()} × {self._region.height()} px"
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            f = QFont(); f.setPointSize(10); f.setBold(True)
            p.setFont(f)
            fm = p.fontMetrics()
            w, h = fm.horizontalAdvance(label) + 14, fm.height() + 8
            box = QRect(int(rect.left()) + 4, int(rect.top()) + 4, w, h)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 170))
            p.drawRoundedRect(box, 4, 4)
            p.setPen(QColor("white"))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, label)
        p.end()


# --------------------------------------------------------------------------- #
#  Ikony
# --------------------------------------------------------------------------- #
def make_icon(recording: bool) -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#D32F2F") if recording else QColor("#455A64"))
    p.drawEllipse(4, 4, 56, 56)
    p.setBrush(QColor("white"))
    if recording:
        p.drawRoundedRect(21, 21, 22, 22, 3, 3)
    else:
        p.drawEllipse(19, 19, 26, 26)
    p.end()
    return QIcon(pm)


# --------------------------------------------------------------------------- #
#  Hlavné okno
# --------------------------------------------------------------------------- #
class RecorderWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setWindowIcon(make_icon(False))
        self.setMinimumWidth(560)

        self.settings = QSettings(ORG_NAME, "ScreenRecorder")
        self.monitors: list[Monitor] = list_monitors()
        self.audio_devices: list[AudioDevice] = []
        self.region: QRect | None = None
        self.output_path = ""
        self.process: QProcess | None = None
        self.started_at: datetime | None = None
        self._hidden_for_recording = False
        self.restart_requested = False
        self._selector: RegionSelector | None = None
        self._frames: list[RegionFrame] = []
        self._picking_region = False
        self._stopping = False

        self._build_ui()
        self._build_tray()
        self._load_settings()
        self._detect_ffmpeg()

        app = QApplication.instance()
        app.screenAdded.connect(lambda _s: self._rebuild_region_frames())
        app.screenRemoved.connect(lambda _s: self._rebuild_region_frames())

        self.tick = QTimer(self)
        self.tick.setInterval(500)
        self.tick.timeout.connect(self._update_status)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # ---- FFmpeg
        ff_box = QGroupBox("FFmpeg")
        ff_row = QHBoxLayout(ff_box)
        self.ffmpeg_edit = QLineEdit()
        self.ffmpeg_edit.setPlaceholderText(tr("cesta k ffmpeg.exe (hľadá sa automaticky v PATH a vedľa skriptu)"))
        self.ffmpeg_edit.editingFinished.connect(self._detect_ffmpeg)
        ff_browse = QPushButton(tr("Prehľadávať…"))
        ff_browse.clicked.connect(self._browse_ffmpeg)
        ff_row.addWidget(self.ffmpeg_edit, 1)
        ff_row.addWidget(ff_browse)
        root.addWidget(ff_box)

        # ---- Obraz
        video_box = QGroupBox(tr("Obraz"))
        video = QVBoxLayout(video_box)

        row_full = QHBoxLayout()
        self.radio_full = QRadioButton(tr("Celá obrazovka"))
        self.radio_full.setChecked(True)
        self.monitor_combo = QComboBox()
        self.monitor_combo.addItem(tr("Všetky monitory (celá pracovná plocha)"), None)
        for i, m in enumerate(self.monitors):
            suffix = tr(" – hlavný") if m.primary else ""
            self.monitor_combo.addItem(f"Monitor {i + 1}: {m.width}×{m.height}{suffix}", i)
        row_full.addWidget(self.radio_full)
        row_full.addWidget(self.monitor_combo, 1)
        video.addLayout(row_full)

        row_region = QHBoxLayout()
        self.radio_region = QRadioButton(tr("Vybraná oblasť"))
        self.region_btn = QPushButton(tr("Vybrať oblasť…"))
        self.region_btn.clicked.connect(self._pick_region)
        self.region_label = QLabel(tr("žiadna oblasť nie je vybraná"))
        self.region_label.setStyleSheet("color: #777;")
        row_region.addWidget(self.radio_region)
        row_region.addWidget(self.region_btn)
        row_region.addWidget(self.region_label, 1)
        video.addLayout(row_region)

        self.radio_full.toggled.connect(self._sync_mode_widgets)
        self.radio_region.toggled.connect(self._sync_mode_widgets)

        form = QFormLayout()
        form.setContentsMargins(0, 6, 0, 0)
        self.fps_combo = QComboBox()
        for f in FPS_OPTIONS:
            self.fps_combo.addItem(f"{f} fps", f)
        self.fps_combo.setCurrentIndex(FPS_OPTIONS.index(30))
        self.encoder_combo = QComboBox()
        self.quality_combo = QComboBox()
        for key in QUALITY:
            self.quality_combo.addItem(tr(QUALITY_LABELS[key]), key)
        self.quality_combo.setCurrentIndex(self.quality_combo.findData("medium"))
        self.cursor_check = QCheckBox(tr("Zaznamenať kurzor myši"))
        self.cursor_check.setChecked(True)
        form.addRow(tr("Snímková frekvencia:"), self.fps_combo)
        form.addRow(tr("Kodér:"), self.encoder_combo)
        form.addRow(tr("Kvalita:"), self.quality_combo)
        form.addRow("", self.cursor_check)
        video.addLayout(form)
        root.addWidget(video_box)

        # ---- Zvuk
        audio_box = QGroupBox(tr("Zvuk"))
        audio = QVBoxLayout(audio_box)

        row_a1 = QHBoxLayout()
        self.audio_check = QCheckBox(tr("Nahrávať zvuk zo zariadenia:"))
        self.audio_check.setChecked(True)
        self.audio_combo = QComboBox()
        self.audio_refresh = QPushButton(tr("Obnoviť"))
        self.audio_refresh.clicked.connect(self._refresh_audio_devices)
        row_a1.addWidget(self.audio_check)
        row_a1.addWidget(self.audio_combo, 1)
        row_a1.addWidget(self.audio_refresh)
        audio.addLayout(row_a1)

        row_a2 = QHBoxLayout()
        self.audio2_check = QCheckBox(tr("Zmiešať s druhým zariadením:"))
        self.audio2_combo = QComboBox()
        self.audio2_combo.setEnabled(False)
        self.audio2_check.toggled.connect(self.audio2_combo.setEnabled)
        row_a2.addWidget(self.audio2_check)
        row_a2.addWidget(self.audio2_combo, 1)
        audio.addLayout(row_a2)

        hint = QLabel(tr(
            "Zvuk systému („čo počujem“) sa nahrá cez zariadenie <b>Stereo Mix</b> "
            "(zapni ho v Nastavenia › Zvuk › Nahrávanie) alebo cez virtuálny kábel (VB-Cable). "
            "Mikrofón + systém zmiešaš zapnutím druhého zariadenia."
        ))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #777;")
        audio.addWidget(hint)
        root.addWidget(audio_box)

        # ---- Výstup
        out_box = QGroupBox(tr("Výstup"))
        out = QVBoxLayout(out_box)
        row_o = QHBoxLayout()
        self.out_edit = QLineEdit()
        out_browse = QPushButton(tr("Prehľadávať…"))
        out_browse.clicked.connect(self._browse_output)
        row_o.addWidget(QLabel(tr("Priečinok:")))
        row_o.addWidget(self.out_edit, 1)
        row_o.addWidget(out_browse)
        out.addLayout(row_o)
        self.hide_check = QCheckBox(
            tr("Skryť toto okno počas nahrávania (zastavíš cez ikonu v lište alebo {hotkey})").format(hotkey=HOTKEY_LABEL))
        self.hide_check.setChecked(True)
        out.addWidget(self.hide_check)
        root.addWidget(out_box)

        # ---- Ovládanie
        ctl = QHBoxLayout()
        self.record_btn = QPushButton(tr("●  Nahrávať"))
        self.record_btn.setMinimumHeight(44)
        self.record_btn.setStyleSheet(
            "QPushButton { font-size: 15px; font-weight: 600; padding: 6px 22px;"
            "  color: white; background-color: #D32F2F; border: 1px solid #B71C1C; border-radius: 6px; }"
            "QPushButton:hover { background-color: #E53935; }"
            "QPushButton:pressed { background-color: #B71C1C; }"
            "QPushButton:disabled { color: #F5F5F5; background-color: #EF9A9A; border-color: #E57373; }"
        )
        self.record_btn.clicked.connect(self.toggle_recording)
        self.open_btn = QPushButton(tr("Otvoriť priečinok"))
        self.open_btn.clicked.connect(self._open_output_folder)
        self.status_label = QLabel(tr("Pripravené."))
        ctl.addWidget(self.record_btn)
        ctl.addWidget(self.open_btn)
        ctl.addWidget(self.status_label, 1)
        root.addLayout(ctl)

        # ---- Log + jazyk
        bottom = QHBoxLayout()
        self.log_check = QCheckBox(tr("Zobraziť výstup FFmpeg"))
        self.log_check.toggled.connect(self._toggle_log)
        self.language_combo = QComboBox()
        for code, name in LANGUAGES:
            self.language_combo.addItem(name, code)
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        bottom.addWidget(self.log_check, 1)
        bottom.addWidget(QLabel(tr("Jazyk:")))
        bottom.addWidget(self.language_combo)
        root.addLayout(bottom)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setFont(QFont("Consolas" if IS_WINDOWS else "Monospace", 9))
        self.log.setMinimumHeight(180)
        self.log.hide()
        root.addWidget(self.log)

        self._sync_mode_widgets()

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(make_icon(False), self)
        menu = QMenu()
        self.tray_toggle_action = QAction(tr("Nahrávať"), self)
        self.tray_toggle_action.triggered.connect(self.toggle_recording)
        show_action = QAction(tr("Zobraziť okno"), self)
        show_action.triggered.connect(self._show_window)
        quit_action = QAction(tr("Ukončiť"), self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(self.tray_toggle_action)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip(APP_NAME)
        self.tray.activated.connect(self._tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    # ------------------------------------------------------------ nastavenia
    def _load_settings(self) -> None:
        s = self.settings
        self.ffmpeg_edit.setText(s.value("ffmpeg", "", str))
        default_dir = str(Path.home() / "Videos") if IS_WINDOWS else str(Path.home())
        self.out_edit.setText(s.value("output_dir", default_dir, str))
        fps = s.value("fps", 30, int)
        if fps in FPS_OPTIONS:
            self.fps_combo.setCurrentIndex(FPS_OPTIONS.index(fps))
        quality = s.value("quality", "medium", str)
        quality = QUALITY_LEGACY.get(quality, quality)
        idx = self.quality_combo.findData(quality)
        if idx >= 0:
            self.quality_combo.setCurrentIndex(idx)
        idx = self.language_combo.findData(_LANG)
        if idx >= 0:
            self.language_combo.blockSignals(True)
            self.language_combo.setCurrentIndex(idx)
            self.language_combo.blockSignals(False)
        self.cursor_check.setChecked(s.value("cursor", True, bool))
        self.hide_check.setChecked(s.value("hide_window", True, bool))
        self.audio_check.setChecked(s.value("audio", True, bool))
        self.audio2_check.setChecked(s.value("audio2", False, bool))
        if s.value("mode", "full", str) == "region":
            self.radio_region.setChecked(True)
        mon = s.value("monitor", 0, int)
        if 0 <= mon < self.monitor_combo.count():
            self.monitor_combo.setCurrentIndex(mon)

    def _save_settings(self) -> None:
        s = self.settings
        s.setValue("ffmpeg", self.ffmpeg_edit.text().strip())
        s.setValue("output_dir", self.out_edit.text().strip())
        s.setValue("fps", self.fps_combo.currentData())
        s.setValue("encoder", self.encoder_combo.currentData())
        s.setValue("quality", self.quality_combo.currentData())
        s.setValue("cursor", self.cursor_check.isChecked())
        s.setValue("hide_window", self.hide_check.isChecked())
        s.setValue("audio", self.audio_check.isChecked())
        s.setValue("audio2", self.audio2_check.isChecked())
        s.setValue("audio_device", self.audio_combo.currentText())
        s.setValue("audio_device2", self.audio2_combo.currentText())
        s.setValue("mode", "region" if self.radio_region.isChecked() else "full")
        s.setValue("monitor", self.monitor_combo.currentIndex())

    # --------------------------------------------------------------- ffmpeg
    def _detect_ffmpeg(self) -> None:
        path = find_ffmpeg(self.ffmpeg_edit.text().strip())
        if not path:
            self.ffmpeg_path = ""
            self.status_label.setText(tr("FFmpeg sa nenašiel – nainštaluj ho (winget install Gyan.FFmpeg) alebo zadaj cestu."))
            self.status_label.setStyleSheet("color: #C62828;")
            self.encoder_combo.clear()
            self.encoder_combo.addItem(tr(ENCODER_LABELS[0][1]), ENCODER_LABELS[0][0])
            return
        self.ffmpeg_path = path
        if not self.ffmpeg_edit.text().strip():
            self.ffmpeg_edit.setPlaceholderText(path)
        self.status_label.setStyleSheet("")
        self.status_label.setText(tr("Pripravené."))

        wanted = self.settings.value("encoder", "libx264", str)
        self.encoder_combo.clear()
        for name, label in list_video_encoders(path):
            self.encoder_combo.addItem(tr(label), name)
        idx = self.encoder_combo.findData(wanted)
        self.encoder_combo.setCurrentIndex(idx if idx >= 0 else 0)

        self._refresh_audio_devices()

    def _refresh_audio_devices(self) -> None:
        wanted1 = (self.audio_combo.currentText() if isinstance(self.audio_combo.currentData(), AudioDevice)
                   else self.settings.value("audio_device", "", str))
        wanted2 = (self.audio2_combo.currentText() if isinstance(self.audio2_combo.currentData(), AudioDevice)
                   else self.settings.value("audio_device2", "", str))
        self.audio_devices = list_dshow_audio_devices(self.ffmpeg_path) if self.ffmpeg_path else []
        for combo, wanted in ((self.audio_combo, wanted1), (self.audio2_combo, wanted2)):
            combo.clear()
            for dev in self.audio_devices:
                combo.addItem(dev.name, dev)
            idx = combo.findText(wanted)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        if not self.audio_devices:
            self.audio_combo.addItem(tr("(žiadne zvukové zariadenie sa nenašlo)"), None)
            self.audio2_combo.addItem(tr("(žiadne zvukové zariadenie sa nenašlo)"), None)

    # ------------------------------------------------------------- pomocné
    def _sync_mode_widgets(self) -> None:
        full = self.radio_full.isChecked()
        self.monitor_combo.setEnabled(full)
        self.region_btn.setEnabled(not full)
        self._update_region_frame()

    def _language_changed(self, _index: int) -> None:
        lang = str(self.language_combo.currentData() or "sk")
        if lang == _LANG:
            return
        self.settings.setValue("language", lang)
        answer = QMessageBox.question(
            self, APP_NAME, tr("Zmena jazyka sa prejaví po reštarte aplikácie. Reštartovať teraz?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.restart_requested = True
            self._quit()

    def _toggle_log(self, on: bool) -> None:
        self.log.setVisible(on)
        if not on:
            self.adjustSize()

    def _browse_ffmpeg(self) -> None:
        flt = "ffmpeg.exe (ffmpeg.exe)" if IS_WINDOWS else "ffmpeg (ffmpeg)"
        path, _ = QFileDialog.getOpenFileName(self, tr("Vyber ffmpeg"), "", flt + ";;" + tr("Všetky súbory (*)"))
        if path:
            self.ffmpeg_edit.setText(path)
            self._detect_ffmpeg()

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("Priečinok pre nahrávky"), self.out_edit.text())
        if path:
            self.out_edit.setText(path)

    def _open_output_folder(self) -> None:
        target = self.out_edit.text().strip() or str(Path.home())
        Path(target).mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(target))

    def _append_log(self, text: str) -> None:
        text = text.replace("\r\n", "\n").replace("\r", "\n").rstrip()
        if text:
            self.log.appendPlainText(text)

    def _tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._show_window()

    def _show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit(self) -> None:
        if self.process is not None:
            self.stop_recording()
            self.process.waitForFinished(10000)
        self._save_settings()
        self._drop_region_frames()
        self.tray.hide()
        QApplication.quit()

    def _set_recording_ui(self, recording: bool) -> None:
        self.record_btn.setText(tr("■  Zastaviť") if recording else tr("●  Nahrávať"))
        self.tray_toggle_action.setText(tr("Zastaviť nahrávanie") if recording else tr("Nahrávať"))
        icon = make_icon(recording)
        self.tray.setIcon(icon)
        self.setWindowIcon(icon)
        for f in self._frames:
            f.set_locked(recording)
        for w in (
            self.radio_full, self.radio_region, self.monitor_combo, self.region_btn,
            self.fps_combo, self.encoder_combo, self.quality_combo, self.cursor_check,
            self.audio_check, self.audio_combo, self.audio_refresh, self.audio2_check,
            self.audio2_combo, self.out_edit, self.hide_check, self.ffmpeg_edit,
            self.language_combo,
        ):
            w.setEnabled(not recording)
        if not recording:
            self._sync_mode_widgets()
            self.audio2_combo.setEnabled(self.audio2_check.isChecked())

    # ------------------------------------------------------- výber oblasti
    def _pick_region(self) -> None:
        self._selector = RegionSelector(self)
        self._selector.finished.connect(self._region_picked)
        self._picking_region = True
        self._update_region_frame()          # počas výberu rám skryť
        self.hide()
        QTimer.singleShot(250, self._selector.start)

    def _region_picked(self, rect) -> None:
        self._picking_region = False
        self._show_window()
        if rect is not None:
            self.region = rect
            self.radio_region.setChecked(True)
            self._set_region_text(rect)
        self._update_region_frame()

    def _set_region_text(self, rect: QRect) -> None:
        self.region_label.setStyleSheet("")
        self.region_label.setText(f"X {rect.x()}, Y {rect.y()}  –  {rect.width()} × {rect.height()} px")

    def _region_dragged(self, rect: QRect) -> None:
        """Používateľ potiahol hranu rámu – prevziať nový rozmer."""
        self.region = QRect(rect)
        self._set_region_text(rect)
        for f in self._frames:
            f.set_region(self.region)

    # ---- rám vybranej oblasti (viditeľný stále, kým je zvolený režim „Vybraná oblasť“)
    def _update_region_frame(self) -> None:
        show = self.radio_region.isChecked() and self.region is not None and not self._picking_region
        if not show:
            for f in self._frames:
                f.hide()
            return
        if not self._frames:
            self._frames = [RegionFrame(s) for s in QApplication.screens()]
            for f in self._frames:
                f.regionChanged.connect(self._region_dragged)
        for f in self._frames:
            f.set_locked(self.process is not None)
            f.set_region(self.region)
            if not f.isVisible():
                f.show()
                f.setGeometry(f.screen().geometry())

    def _drop_region_frames(self) -> None:
        for f in self._frames:
            f.close()
            f.deleteLater()
        self._frames = []

    def _rebuild_region_frames(self) -> None:
        self._drop_region_frames()
        self._update_region_frame()

    # ------------------------------------------------------------ nahrávanie
    def toggle_recording(self) -> None:
        if self.process is None:
            self.start_recording()
        else:
            self.stop_recording()

    def _selected_audio(self) -> list[AudioDevice]:
        devices: list[AudioDevice] = []
        if self.audio_check.isChecked():
            d1 = self.audio_combo.currentData()
            if isinstance(d1, AudioDevice):
                devices.append(d1)
            if self.audio2_check.isChecked():
                d2 = self.audio2_combo.currentData()
                if isinstance(d2, AudioDevice) and d2.dshow_id != (d1.dshow_id if d1 else None):
                    devices.append(d2)
        return devices

    def _capture_region(self) -> tuple[QRect | None, tuple[int, int]]:
        """Vráti (oblasť pre gdigrab alebo None = celá plocha, odhad rozmerov)."""
        if self.radio_region.isChecked():
            if self.region is None:
                raise ValueError(tr("Najprv vyber oblasť nahrávania."))
            return self.region, (self.region.width(), self.region.height())
        idx = self.monitor_combo.currentData()
        if idx is None:
            union = QRect()
            for m in self.monitors:
                union = union.united(m.rect)
            return None, (max(union.width(), 2), max(union.height(), 2))
        m = self.monitors[idx]
        r = m.rect
        r.setWidth(r.width() - r.width() % 2)
        r.setHeight(r.height() - r.height() % 2)
        return r, (r.width(), r.height())

    def start_recording(self) -> None:
        if self.process is not None:
            return
        if not self.ffmpeg_path:
            QMessageBox.warning(self, APP_NAME, tr("FFmpeg sa nenašiel. Nainštaluj ho alebo zadaj cestu k ffmpeg.exe."))
            return
        try:
            region, est = self._capture_region()
        except ValueError as exc:
            QMessageBox.information(self, APP_NAME, str(exc))
            return

        audio = self._selected_audio()
        if self.audio_check.isChecked() and not audio:
            QMessageBox.warning(self, APP_NAME, tr("Nie je vybrané žiadne zvukové zariadenie. Vypni zvuk alebo obnov zoznam zariadení."))
            return

        out_dir = Path(self.out_edit.text().strip() or Path.home())
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, tr("Priečinok sa nedá vytvoriť:\n{exc}").format(exc=exc))
            return
        self.output_path = str(out_dir / f"zaznam_{datetime.now():%Y-%m-%d_%H-%M-%S}.mp4")

        args = build_ffmpeg_args(
            fps=int(self.fps_combo.currentData()),
            region=region,
            cursor=self.cursor_check.isChecked(),
            encoder=str(self.encoder_combo.currentData() or "libx264"),
            quality=str(self.quality_combo.currentData()),
            audio=audio,
            output=self.output_path,
            est_size=est,
        )
        self._save_settings()
        self.log.clear()
        self._append_log("$ " + subprocess.list2cmdline([self.ffmpeg_path, *args]))

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._on_process_output)
        self.process.started.connect(self._on_process_started)
        self.process.errorOccurred.connect(self._on_process_error)
        self.process.finished.connect(self._on_process_finished)
        self._stopping = False

        self._set_recording_ui(True)
        self.status_label.setText(tr("Spúšťa sa…"))

        if self.hide_check.isChecked() and self.tray.isVisible():
            self._hidden_for_recording = True
            self.hide()
            # počkaj, kým okno zmizne z obrazovky, až potom začni nahrávať
            QTimer.singleShot(400, lambda: self._launch(args))
        else:
            self._hidden_for_recording = False
            self._launch(args)

    def _launch(self, args: list[str]) -> None:
        if self.process is None:
            return
        self.process.start(self.ffmpeg_path, args)

    def stop_recording(self) -> None:
        if self.process is None or self._stopping:
            return
        self._stopping = True
        self.status_label.setText(tr("Ukončuje sa nahrávanie…"))
        if self.process.state() == QProcess.ProcessState.Running:
            # 'q' na stdin = korektné ukončenie, MP4 sa riadne uzavrie
            self.process.write(b"q")
            self.process.waitForBytesWritten(1000)
            QTimer.singleShot(15000, self._force_stop)
        else:
            # ffmpeg sa ešte nespustil (čaká sa na skrytie okna) – len upratať
            proc = self.process
            self.process = None
            proc.deleteLater()
            self._stopping = False
            self._set_recording_ui(False)
            self.status_label.setStyleSheet("")
            self.status_label.setText(tr("Nahrávanie zrušené."))
            if self._hidden_for_recording:
                self._hidden_for_recording = False
                self._show_window()

    def _force_stop(self) -> None:
        if self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning:
            self._append_log(tr("FFmpeg neskončil včas – vynútené ukončenie."))
            self.process.kill()

    # ------------------------------------------------------- proces (sloty)
    def _on_process_started(self) -> None:
        self.started_at = datetime.now()
        self.tick.start()
        self._update_status()
        if self.tray.isVisible():
            self.tray.showMessage(APP_NAME, tr("Nahrávanie beží. Zastavíš ho cez {hotkey} alebo ikonu v lište.").format(hotkey=HOTKEY_LABEL),
                                  QSystemTrayIcon.MessageIcon.Information, 3000)

    def _on_process_output(self) -> None:
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardOutput())
        self._append_log(data.decode("utf-8", errors="replace"))

    def _on_process_error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._append_log(tr("FFmpeg sa nepodarilo spustiť: ") + self.ffmpeg_path)
            QTimer.singleShot(0, lambda: self._on_process_finished(-1, None))

    def _on_process_finished(self, exit_code: int, _status) -> None:
        if self.process is None:
            return
        self.tick.stop()
        proc = self.process
        self.process = None
        self._set_recording_ui(False)
        if proc is not None:
            proc.deleteLater()

        if self._hidden_for_recording:
            self._hidden_for_recording = False
            self._show_window()

        size = Path(self.output_path).stat().st_size if Path(self.output_path).is_file() else 0
        if exit_code == 0 or (self._stopping and size > 0):
            self.status_label.setStyleSheet("")
            self.status_label.setText(tr("Uložené: {name} ({size})").format(name=Path(self.output_path).name, size=self._fmt_size(size)))
            if self.tray.isVisible():
                self.tray.showMessage(APP_NAME, tr("Nahrávka uložená:\n{path}").format(path=self.output_path),
                                      QSystemTrayIcon.MessageIcon.Information, 4000)
        else:
            self.status_label.setStyleSheet("color: #C62828;")
            self.status_label.setText(tr("FFmpeg skončil s chybou (kód {code}).").format(code=exit_code))
            tail = "\n".join(self.log.toPlainText().splitlines()[-12:])
            self.log_check.setChecked(True)
            QMessageBox.critical(self, APP_NAME, tr("Nahrávanie zlyhalo. Posledné riadky výstupu FFmpeg:\n\n") + tail)
        self._stopping = False

    def _update_status(self) -> None:
        if self.started_at is None:
            return
        elapsed = int((datetime.now() - self.started_at).total_seconds())
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        size = Path(self.output_path).stat().st_size if Path(self.output_path).is_file() else 0
        text = tr("● Nahráva sa") + f"  {h:02d}:{m:02d}:{s:02d}   {self._fmt_size(size)}"
        self.status_label.setStyleSheet("color: #C62828; font-weight: 600;")
        self.status_label.setText(text)
        self.tray.setToolTip(f"{APP_NAME} – {text}")

    @staticmethod
    def _fmt_size(size: int) -> str:
        if size < 1024 * 1024:
            return f"{size / 1024:.0f} kB"
        if size < 1024 ** 3:
            return f"{size / 1024 ** 2:.1f} MB"
        return f"{size / 1024 ** 3:.2f} GB"

    # ----------------------------------------------------------- udalosti
    def closeEvent(self, event) -> None:
        if self.process is not None:
            answer = QMessageBox.question(
                self, APP_NAME, tr("Nahrávanie stále beží. Zastaviť ho a ukončiť aplikáciu?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.stop_recording()
            if self.process is not None:
                self.process.waitForFinished(10000)
        self._save_settings()
        self._drop_region_frames()
        self.tray.hide()
        event.accept()
        QApplication.quit()


# --------------------------------------------------------------------------- #
def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORG_NAME)
    app.setQuitOnLastWindowClosed(False)

    # jazyk: nastavenie (zapisuje ho aj inštalátor) alebo jazyk Windows
    set_language(detect_language(QSettings(ORG_NAME, "ScreenRecorder")))
    qt_translator = QTranslator(app)
    if _LANG != "en" and qt_translator.load(
        "qtbase_" + _LANG, QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    ):
        app.installTranslator(qt_translator)   # Áno/Nie a pod. v Qt dialógoch

    # jediná inštancia (druhé spustenie – napr. z autoštartu + zástupcu – len upozorní)
    lock = QLockFile(QDir.tempPath() + "/draftex-screen-recorder.lock")
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        QMessageBox.information(None, APP_NAME, tr("Aplikácia už beží – nájdeš ju ako ikonu v lište vedľa hodín."))
        return 0

    window = RecorderWindow()

    hotkey_filter = None
    if register_global_hotkey():
        hotkey_filter = HotkeyFilter(window.toggle_recording)
        app.installNativeEventFilter(hotkey_filter)
    else:
        window.hide_check.setText(tr("Skryť toto okno počas nahrávania (zastavíš cez ikonu v lište)"))

    # --tray: spustiť len do lišty (autoštart s Windows), inak zobraziť okno
    if "--tray" in sys.argv[1:] and window.tray.isVisible():
        window.tray.showMessage(APP_NAME, tr("Beží na pozadí. Nahrávanie: {hotkey} alebo dvojklik na ikonu.").format(hotkey=HOTKEY_LABEL),
                                QSystemTrayIcon.MessageIcon.Information, 3000)
    else:
        window.show()

    code = app.exec()
    unregister_global_hotkey()
    lock.unlock()

    if window.restart_requested:
        # reštart po zmene jazyka (bez --tray, nech je okno hneď vidieť)
        args = [a for a in sys.argv[1:] if a != "--tray"]
        if not getattr(sys, "frozen", False):
            args = [sys.argv[0], *args]
        QProcess.startDetached(sys.executable, args)
    return code


if __name__ == "__main__":
    sys.exit(main())
