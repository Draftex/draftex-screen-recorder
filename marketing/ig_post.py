"""Vygeneruje IG grafiku 1080x1080 (marketing/ig_post.png) so snímkou aplikácie.

Spustenie (z koreňa projektu):  .venv\\Scripts\\python.exe marketing\\ig_post.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_SCALE_FACTOR", "2")   # ostrá snímka okna (2x)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QEventLoop, QRect, QRectF, QTimer, Qt  # noqa: E402
from PyQt6.QtGui import (QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient)  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import screen_recorder as sr  # noqa: E402

OUT = Path(__file__).with_name("ig_post.png")
W = H = 1080


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def grab_app_window(app: QApplication) -> QImage:
    """Slovenské okno aplikácie s neutrálnymi hodnotami (bez osobných ciest)."""
    sr.set_language("sk")
    w = sr.RecorderWindow()
    w.ffmpeg_edit.setText(r"C:\Program Files\Draftex\Screen Recorder\ffmpeg.exe")
    w.out_edit.setText(r"C:\Users\Rado\Videos")
    w.radio_region.setChecked(True)
    w.region = QRect(640, 360, 1280, 720)
    w._set_region_text(w.region)
    w.fps_combo.setCurrentIndex(sr.FPS_OPTIONS.index(30))
    w.quality_combo.setCurrentIndex(w.quality_combo.findData("medium"))
    w.show()
    wait(300)
    w.setFocus()                      # bez kurzora v textovom poli (spustí editingFinished -> detekcia)
    w.ffmpeg_edit.deselect()
    wait(200)
    # až po detekcii ffmpeg – ukážkové zariadenia a stav
    for combo in (w.audio_combo, w.audio2_combo):
        combo.clear()
    w.audio_combo.addItem("Mikrofón (Realtek High Definition Audio)")
    w.audio2_combo.addItem("Stereo Mix (Realtek High Definition Audio)")
    w.audio_check.setChecked(True)
    w.audio2_check.setChecked(True)
    w.status_label.setStyleSheet("")
    w.status_label.setText("Pripravené.")
    wait(100)
    img = w.grab().toImage()
    w._drop_region_frames()
    w.tray.hide()
    w.hide()
    return img


def pick_font() -> str:
    from PyQt6.QtGui import QFontDatabase
    have = set(QFontDatabase.families())
    for fam in ("Plus Jakarta Sans", "Manrope", "Inter", "Segoe UI Variable Display", "Segoe UI"):
        if fam in have:
            return fam
    return "Segoe UI"


def rounded(p: QPainter, rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def main() -> None:
    app = QApplication(sys.argv)
    shot = grab_app_window(app)

    img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    fam = pick_font()

    # pozadie – tmavá modrá ako web draftex.sk, jemná azúrová žiara vpravo hore
    g = QLinearGradient(0, 0, W, H)
    g.setColorAt(0.0, QColor("#0B1526"))
    g.setColorAt(1.0, QColor("#0F1B30"))
    p.fillRect(0, 0, W, H, g)
    glow = QRadialGradient(W - 40, 40, 640)
    glow.setColorAt(0.0, QColor(56, 182, 255, 80))
    glow.setColorAt(1.0, QColor(56, 182, 255, 0))
    p.fillRect(0, 0, W, H, glow)

    # zelený štítok ako na webe
    badge_font = QFont(fam, 15, QFont.Weight.Bold)
    badge_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 112)
    p.setFont(badge_font)
    fm = p.fontMetrics()
    badge_text = "ZADARMO NA STIAHNUTIE"
    badge = QRectF(72, 64, fm.horizontalAdvance(badge_text) + 44, 46)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(34, 197, 94, 40))
    p.drawPath(rounded(p, badge, 23))
    p.setPen(QColor("#4ADE80"))
    p.drawText(badge.toRect(), Qt.AlignmentFlag.AlignCenter, badge_text)

    # titulok
    p.setFont(QFont(fam, 48, QFont.Weight.Bold))
    p.setPen(QColor("white"))
    p.drawText(QRect(72, 130, 960, 80), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Draftex Screen Recorder")
    p.setPen(QColor("#38B6FF"))
    p.drawText(QRect(72, 208, 960, 80), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Nahrávaj obrazovku zadarmo.")

    # podtitul
    p.setFont(QFont(fam, 21))
    p.setPen(QColor("#AEB9CF"))
    p.drawText(QRect(72, 312, 960, 72), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
               "Celá plocha, jeden monitor alebo vybraná oblasť. Do MP4 vrátane zvuku, "
               "zachytí aj kontextové menu a popupy. Nahrávanie spustíš skratkou.")

    # CTA – azúrové tlačidlo ako na webe
    cta = QRectF(72, 412, 470, 74)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 70))
    p.drawPath(rounded(p, cta.translated(0, 8), 37))
    p.setBrush(QColor("#2EA8FF"))
    p.drawPath(rounded(p, cta, 37))
    p.setFont(QFont(fam, 24, QFont.Weight.Bold))
    p.setPen(QColor("#06192E"))
    p.drawText(cta.toRect(), Qt.AlignmentFlag.AlignCenter, "Stiahnuť zadarmo  ↓")

    p.setFont(QFont(fam, 22, QFont.Weight.DemiBold))
    p.setPen(QColor("white"))
    p.drawText(QRect(566, 412, 460, 74), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "draftex.sk")

    # parametre ako na webe
    p.setFont(QFont(fam, 18))
    p.setPen(QColor("#8FA0BD"))
    dots = "Windows 10 / 11   •   64-bit   •   82 MB   •   Slovenčina / English"
    p.drawText(QRect(72, 500, 960, 34), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, dots)

    # snímka okna – zaoblené horné rohy, tieň, vybieha zo spodného okraja
    target_w = 800
    scale = target_w / shot.width()
    target_h = int(shot.height() * scale)
    shot_rect = QRectF((W - target_w) / 2, 566, target_w, target_h)
    p.setPen(Qt.PenStyle.NoPen)
    for i in range(18, 0, -2):
        p.setBrush(QColor(0, 0, 0, 10))
        p.drawPath(rounded(p, shot_rect.adjusted(-i, -i + 8, i, i), 26 + i))
    p.save()
    p.setClipPath(rounded(p, shot_rect, 22))
    p.drawImage(shot_rect, shot)
    p.restore()
    p.setPen(QPen(QColor(56, 182, 255, 70), 2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(rounded(p, shot_rect.adjusted(1, 1, -1, -1), 22))

    # jemné stmavnutie spodného okraja, nech snímka „vybieha"
    fade = QLinearGradient(0, H - 160, 0, H)
    fade.setColorAt(0.0, QColor(11, 21, 38, 0))
    fade.setColorAt(1.0, QColor(11, 21, 38, 210))
    p.fillRect(0, H - 160, W, 160, fade)

    p.end()
    img.save(str(OUT))
    print("saved", OUT, img.width(), "x", img.height())


if __name__ == "__main__":
    main()
