' ReelRecon Installer Launcher
' Double-click this file to install ReelRecon without a console window

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the directory where this script lives
scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
installerPath = scriptPath & "\ReelRecon-Installer.pyw"

' Find pythonw.exe
pythonwPath = ""

' Check common locations
If fso.FileExists("C:\Python312\pythonw.exe") Then
    pythonwPath = "C:\Python312\pythonw.exe"
ElseIf fso.FileExists("C:\Python311\pythonw.exe") Then
    pythonwPath = "C:\Python311\pythonw.exe"
ElseIf fso.FileExists("C:\Python310\pythonw.exe") Then
    pythonwPath = "C:\Python310\pythonw.exe"
Else
    ' Try to find via where command
    Set objExec = WshShell.Exec("where pythonw.exe")
    pythonwPath = Trim(objExec.StdOut.ReadLine())
End If

If pythonwPath = "" Or Not fso.FileExists(pythonwPath) Then
    MsgBox "Python not found. Please install Python 3.12 from python.org", vbCritical, "ReelRecon Installer"
    WScript.Quit
End If

' Run the installer with pythonw (no console)
WshShell.Run """" & pythonwPath & """ """ & installerPath & """", 0, False
