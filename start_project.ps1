#to run
# powershell -ExecutionPolicy Bypass -File .\start_project.ps1
# Project paths
$projectPath = "C:\Users\User\Downloads\AI_study_companion"
$pythonPath = "C:\Users\User\AppData\Local\Programs\Python\Python314\python.exe"

# Start backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$projectPath'; & '$pythonPath' -m uvicorn backend.main:app --reload"

# Start frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$projectPath\frontend'; fnm env --shell powershell | Out-String | Invoke-Expression; fnm use 24; npm.cmd run dev"
