@echo off
rem Runs chartgen with the venv next to this file. Model weights and bundled tools live here too.
set "APP=%~dp0"
set "HF_HOME=%APP%models"
set "TORCH_HOME=%APP%models"
set "PATH=%APP%tools;%PATH%"
"%APP%.venv\Scripts\python.exe" "%APP%chartgen.py" %*
