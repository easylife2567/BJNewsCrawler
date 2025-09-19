@echo off
rem echo %~d0
%~d0
cd %cd%

set pan=""
if exist C:\Anaconda3\python.exe (
  set pan=C:
)
if exist D:\Anaconda3\python.exe (
  set pan=D:
)

if %pan%=="" (
  echo 找不到Anaconda3\Python.exe，退出！
  goto endp
)

set appdisk=D:\CENTER\Python\报纸下载

@CALL %pan%\Anaconda3\Scripts\activate.bat  %pan%\Anaconda3
echo %cd%
rem echo %PATH%

echo 运行 %appdisk%\xinjing.py
%pan%\Anaconda3\python.exe %appdisk%\xinjing.py

rem shutdown.exe -s -t 600

pause

:endp

@echo on
