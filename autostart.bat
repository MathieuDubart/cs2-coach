@echo off
rem Lance le serveur Coach CS2 en arriere-plan a chaque ouverture de session Windows.
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
powershell -NoProfile -Command "$w=(Get-Command pythonw).Source; $s=(New-Object -ComObject WScript.Shell).CreateShortcut('%STARTUP%\Coach CS2.lnk'); $s.TargetPath=$w; $s.Arguments='serve.py --no-browser'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.Save()"
start "" pythonw serve.py --no-browser
echo Demarrage automatique active. L'app est disponible sur http://127.0.0.1:8765
echo Pour le desactiver : supprime "Coach CS2" dans le dossier Demarrage (Win+R, shell:startup).
pause
