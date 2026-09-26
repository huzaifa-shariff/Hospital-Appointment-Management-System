Set shell = CreateObject("WScript.Shell")
script = "C:\Users\huzai\OneDrive\Documents\ChatGPT\Hospital Appointment Management System 2\start_hospital_flask.ps1"
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & script & """", 0, False
