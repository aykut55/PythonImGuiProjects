@echo off
REM ============================================================
REM  PythonDataPlotter - ilk kurulum
REM  dearpygui==2.3.1
REM  imgui-bundle==1.92.801
REM  .venv olusturur + requirements kurar + .vscode ayarlar + main.py + runMe.bat
REM  Tekrar calistirilabilir (var olanlari atlar).
REM ============================================================
setlocal
cd /d "%~dp0"

echo === PythonDataPlotter setup ===
echo.

REM --- 1) sanal ortam (.venv) ---
if exist ".venv\Scripts\python.exe" (
    echo [1/5] .venv zaten var, atlaniyor.
) else (
    echo [1/5] .venv olusturuluyor...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo HATA: venv olusturulamadi. Python 3 kurulu mu?  ^(py -3 --version^)
        pause
        exit /b 1
    )
)

REM --- 2) bagimliliklar ---
echo [2/5] pip + requirements kuruluyor...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo HATA: paket kurulumu basarisiz.
    pause
    exit /b 1
)

REM --- 3) .vscode ayarlari (yoksa olustur) ---
echo [3/5] .vscode ayarlari...
if not exist ".vscode" mkdir ".vscode"
if not exist ".vscode\settings.json" call :write_settings
if not exist ".vscode\launch.json"  call :write_launch

REM --- 4) main.py (yoksa olustur) ---
if exist "main.py" (
    echo [4/5] main.py zaten var, atlaniyor.
) else (
    echo [4/5] main.py olusturuluyor...
    call :write_main
)

REM --- 5) runMe.bat (yoksa olustur) ---
if exist "runMe.bat" (
    echo [5/5] runMe.bat zaten var, atlaniyor.
) else (
    echo [5/5] runMe.bat olusturuluyor...
    call :write_runme
)

echo.
echo === Bitti! Calistir: runMe.bat  ya da VS Code'da F5 ===
echo (VS Code: Ctrl+Shift+P ^> Python: Select Interpreter ^> .venv\Scripts\python.exe)
pause
exit /b 0

REM ------------------------------------------------------------
REM NOT: JSON'da forward slash (/) kullaniliyor -> batch echo backslash'i bozuyor,
REM VS Code Windows'ta / yollari kabul eder.
:write_settings
>".vscode\settings.json"  echo {
>>".vscode\settings.json" echo     "python.defaultInterpreterPath": "${workspaceFolder}/.venv/Scripts/python.exe",
>>".vscode\settings.json" echo     "python.terminal.activateEnvironment": true
>>".vscode\settings.json" echo }
goto :eof

:write_launch
>".vscode\launch.json"  echo {
>>".vscode\launch.json" echo     "version": "0.2.0",
>>".vscode\launch.json" echo     "configurations": [
>>".vscode\launch.json" echo         {
>>".vscode\launch.json" echo             "name": "Run main.py (.venv)",
>>".vscode\launch.json" echo             "type": "debugpy",
>>".vscode\launch.json" echo             "request": "launch",
>>".vscode\launch.json" echo             "program": "${workspaceFolder}/main.py",
>>".vscode\launch.json" echo             "console": "integratedTerminal",
>>".vscode\launch.json" echo             "cwd": "${workspaceFolder}",
>>".vscode\launch.json" echo             "python": "${workspaceFolder}/.venv/Scripts/python.exe"
>>".vscode\launch.json" echo         }
>>".vscode\launch.json" echo     ]
>>".vscode\launch.json" echo }
goto :eof

:write_main
>"main.py"  echo import locale
>>"main.py" echo import subprocess
>>"main.py" echo.
>>"main.py" echo from imgui_bundle import imgui, immapp
>>"main.py" echo.
>>"main.py" echo.
>>"main.py" echo class App:
>>"main.py" echo     def __init__(self):
>>"main.py" echo         try:
>>"main.py" echo             locale.setlocale(locale.LC_TIME, "tr_TR.UTF-8")
>>"main.py" echo         except locale.Error:
>>"main.py" echo             try:
>>"main.py" echo                 locale.setlocale(locale.LC_TIME, "Turkish_Turkey.1254")
>>"main.py" echo             except locale.Error:
>>"main.py" echo                 pass
>>"main.py" echo.
>>"main.py" echo     def gui(self):
>>"main.py" echo         imgui.text("Hello World")
>>"main.py" echo.
>>"main.py" echo     def run(self):
>>"main.py" echo         subprocess.call("cls", shell=True)
>>"main.py" echo         immapp.run(
>>"main.py" echo             gui_function=self.gui,
>>"main.py" echo             window_title="DearImGuiBundleDataPlotter",
>>"main.py" echo             window_size=(800, 600),
>>"main.py" echo         )
>>"main.py" echo.
>>"main.py" echo.
>>"main.py" echo if __name__ == "__main__":
>>"main.py" echo     app = App()
>>"main.py" echo     app.run()
goto :eof

:write_runme
>"runMe.bat"  echo @echo off
>>"runMe.bat" echo REM Yerel .venv ile main.py yi calistirir.
>>"runMe.bat" echo cd /d "%%~dp0"
>>"runMe.bat" echo ".venv\Scripts\python.exe" "%%~dp0main.py"
>>"runMe.bat" echo pause
goto :eof
