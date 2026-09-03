# Draftex Screen Recorder – build inštalačného balíka

Nahrávanie obrazovky (celá plocha / monitor / vybraná oblasť) do MP4 vrátane zvuku
zo zvukových zariadení Windows. Zachytí aj kontextové menu, popupy a tooltipy.

## Obsah

| Súbor | Účel |
|---|---|
| `screen_recorder.py` | aplikácia (PyQt6, volá `ffmpeg.exe`) |
| `screen_recorder.spec` | PyInstaller konfigurácia (onedir, bez konzoly, ikona, version info) |
| `version_info.txt` | Windows „Podrobnosti" súboru EXE (firma, verzia, popis) |
| `icon.ico` | ikona EXE a inštalátora |
| `installer.iss` | Inno Setup 6 skript (slovenčina + angličtina) |
| `build.bat` | celý build jedným spustením |
| `requirements.txt` | PyQt6 + PyInstaller |

## Požiadavky na build PC

1. **Python 3.11** (64-bit) – https://www.python.org/downloads/windows/
2. **Inno Setup 6.3+** – https://jrsoftware.org/isdl.php
   (voliteľné; bez neho vznikne len prenositeľná verzia v `dist\`)
3. internet na prvé stiahnutie FFmpeg (~170 MB), alebo skopíruj vlastný
   `ffmpeg.exe` do priečinka `ffmpeg\` – potom sa nič nesťahuje

## Build

```
build.bat
```

Výsledok:

- `installer\DraftexScreenRecorder-Setup-1.0.0.exe` – inštalátor
- `dist\DraftexScreenRecorder\` – prenositeľná verzia (stačí skopírovať a spustiť `DraftexScreenRecorder.exe`)

## Nová verzia

Zmeň číslo na troch miestach:

1. `screen_recorder.py` → `APP_VERSION = "1.0.0"`
2. `version_info.txt` → `filevers`, `prodvers`, `FileVersion`, `ProductVersion`
3. `installer.iss` → `#define MyAppVersion "1.0.0"`

## Jazyk aplikácie

Zdrojový jazyk je slovenčina, angličtina je slovník `TR_EN` v `screen_recorder.py`
(funkcia `tr()`). Poradie určenia jazyka: hodnota `language` v registri (zapíše ju
inštalátor alebo prepínač „Jazyk" v okne) → jazyk Windows (slovenčina → `sk`, inak `en`).
Pri pridaní nového textu do UI ho obal do `tr("…")` a doplň preklad do `TR_EN`.

## Podpísanie (EV certifikát)

- pred spustením pridaj signtool do PATH (cesta s medzerami v `SIGN_CMD` nesmie byť
  v úvodzovkách, cmd by ju pri odovzdaní do ISCC rozbil) a nastav príkaz:
  ```
  set "PATH=C:\Program Files (x86)\Windows Kitsin.0.26100.0d;%PATH%"
  set SIGN_CMD=signtool sign /sha1 <odtlačok certifikátu> /fd sha256 /tr http://ts.ssl.com /td sha256
  ```
- `build.bat` ním podpíše `dist\...\DraftexScreenRecorder.exe` a cez `ISCC /DSIGN "/Sdraftex=..."`
  aj inštalátor a uninstaller (v `installer.iss` je to za `#ifdef SIGN`)
- bez `SIGN_CMD` vznikne nepodpísaný build

## FFmpeg – licencia

`build.bat` sťahuje statický build FFmpeg (BtbN, **GPL**, obsahuje libx264 + NVENC/AMF/QSV).
FFmpeg beží ako samostatný proces (`ffmpeg.exe` vedľa aplikácie), aplikácia naň nie je
linkovaná; do balíka sa priloží jeho `LICENSE-ffmpeg.txt`. Pri distribúcii zákazníkom
je vhodné v dokumentácii uviesť, že produkt obsahuje FFmpeg (https://ffmpeg.org) pod GPL,
a na požiadanie sprístupniť jeho zdrojové kódy (BtbN ich zverejňuje pri každom builde).
Ak chceš LGPL-only variant, použi zip `...-win64-lgpl.zip` z rovnakého zdroja – ten však
nemá libx264, ostanú len hardvérové kodéry.

## Inštalátor

- inštaluje bez admin práv do `%LocalAppData%\Programs\Draftex\Screen Recorder`
  (dialóg ponúkne aj inštaláciu pre všetkých používateľov do Program Files)
- výber jazyka (slovenčina / angličtina) sa zobrazí vždy; zvolený jazyk sa zapíše do
  `HKCU\Software\Draftex\ScreenRecorder\language` (`sk` / `en`) a aplikácia ho prevezme
- voliteľná úloha „Spúšťať pri prihlásení" → `DraftexScreenRecorder.exe --tray`
  (beží len v lište, nahrávanie cez Ctrl+Shift+F9)
- pri odinštalovaní zmaže aj nastavenia (`HKCU\Software\Draftex\ScreenRecorder`)
- pri aktualizácii Inno Setup zatvorí bežiacu aplikáciu (`CloseApplications=yes`)
