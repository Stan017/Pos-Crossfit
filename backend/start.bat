@echo off
echo Arrancando backend...
start "CrossFit Backend" cmd /k "cd /d %~dp0 && C:\Users\stanley\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.10_qbz5n2kfra8p0\LocalCache\local-packages\Python310\Scripts\uvicorn.exe main:app --reload"

echo Arrancando frontend CrossFit...
start "CrossFit Frontend" cmd /k "cd /d %~dp0..\frontend && npm run dev"

echo Arrancando frontend Medico/Rehab...
start "Medico Frontend" cmd /k "cd /d %~dp0..\frontend-rehab && npm run dev"

echo Arrancando frontend Marketing...
start "Marketing Frontend" cmd /k "cd /d %~dp0..\frontend-marketing && npm run dev"

echo Arrancando frontend Admin...
start "Admin Frontend" cmd /k "cd /d %~dp0..\frontend-admin && npm run dev"

echo.
echo Listo. Todo corriendo en ventanas separadas:
echo   Backend:            http://localhost:8000
echo   Frontend CrossFit:  http://localhost:5173
echo   Frontend Medico:    http://localhost:5174
echo   Frontend Marketing: http://localhost:5175
echo   Frontend Admin:     http://localhost:5176
