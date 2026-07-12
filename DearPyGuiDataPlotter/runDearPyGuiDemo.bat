@echo off
setlocal

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Python venv bulunamadi: %PYTHON_EXE%
    exit /b 1
)

if /I "%~1"=="docs" (
    "%PYTHON_EXE%" -c "import dearpygui.dearpygui as dpg; from dearpygui.demo import show_documentation; dpg.create_context(); dpg.create_viewport(title='DPG Docs', width=1600, height=900); dpg.setup_dearpygui(); show_documentation(); dpg.show_viewport(); dpg.start_dearpygui(); dpg.destroy_context()"
) else (
    "%PYTHON_EXE%" -c "import dearpygui.dearpygui as dpg; from dearpygui.demo import show_demo; dpg.create_context(); dpg.create_viewport(title='DPG Demo', width=1600, height=900); dpg.setup_dearpygui(); show_demo(); dpg.show_viewport(); dpg.start_dearpygui(); dpg.destroy_context()"
)

endlocal
