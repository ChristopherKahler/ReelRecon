' ReelRecon Self-Bootstrapping Installer for Windows
' Downloads Git and Python if needed, then installs ReelRecon

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' URLs for installers
pythonUrl = "https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe"
gitUrl = "https://github.com/git-for-windows/git/releases/download/v2.43.0.windows.1/Git-2.43.0-64-bit.exe"

' Temp folder for downloads
tempFolder = WshShell.ExpandEnvironmentStrings("%TEMP%")

' Function to check if command exists
Function CommandExists(cmd)
    On Error Resume Next
    Set objExec = WshShell.Exec("where " & cmd)
    result = objExec.StdOut.ReadAll()
    CommandExists = (Len(Trim(result)) > 0)
    On Error Goto 0
End Function

' Function to download file using PowerShell
Sub DownloadFile(url, destination)
    psCommand = "powershell -Command ""[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '" & url & "' -OutFile '" & destination & "'"""
    WshShell.Run psCommand, 0, True
End Sub

' Main installation logic
Sub Main()
    Dim needsPython, needsGit
    needsPython = False
    needsGit = False

    ' Check for Python
    If Not CommandExists("python") Then
        needsPython = True
    End If

    ' Check for Git
    If Not CommandExists("git") Then
        needsGit = True
    End If

    ' If dependencies missing, ask user
    If needsPython Or needsGit Then
        msg = "ReelRecon requires the following to be installed:" & vbCrLf & vbCrLf
        If needsPython Then msg = msg & "• Python 3.12" & vbCrLf
        If needsGit Then msg = msg & "• Git" & vbCrLf
        msg = msg & vbCrLf & "Would you like to download and install them automatically?"

        result = MsgBox(msg, vbYesNo + vbQuestion, "ReelRecon Installer")

        If result = vbNo Then
            MsgBox "Please install the required software manually:" & vbCrLf & vbCrLf & _
                   "Python: https://python.org/downloads" & vbCrLf & _
                   "Git: https://git-scm.com/download/win", vbInformation, "ReelRecon Installer"
            WScript.Quit
        End If

        ' Download and install Python
        If needsPython Then
            MsgBox "Downloading Python 3.12..." & vbCrLf & vbCrLf & _
                   "This may take a few minutes. Click OK to start.", vbInformation, "ReelRecon Installer"

            pythonInstaller = tempFolder & "\python-installer.exe"
            DownloadFile pythonUrl, pythonInstaller

            If fso.FileExists(pythonInstaller) Then
                MsgBox "Installing Python..." & vbCrLf & vbCrLf & _
                       "Please follow the Python installer prompts." & vbCrLf & _
                       "IMPORTANT: Check 'Add Python to PATH' option!", vbInformation, "ReelRecon Installer"

                ' Run Python installer (not silent - user should see options)
                WshShell.Run """" & pythonInstaller & """", 1, True
                fso.DeleteFile pythonInstaller
            Else
                MsgBox "Failed to download Python. Please install manually from python.org", vbCritical, "Error"
                WScript.Quit
            End If
        End If

        ' Download and install Git
        If needsGit Then
            MsgBox "Downloading Git..." & vbCrLf & vbCrLf & _
                   "This may take a few minutes. Click OK to start.", vbInformation, "ReelRecon Installer"

            gitInstaller = tempFolder & "\git-installer.exe"
            DownloadFile gitUrl, gitInstaller

            If fso.FileExists(gitInstaller) Then
                MsgBox "Installing Git..." & vbCrLf & vbCrLf & _
                       "Please follow the Git installer prompts." & vbCrLf & _
                       "Default options are fine for most users.", vbInformation, "ReelRecon Installer"

                ' Run Git installer
                WshShell.Run """" & gitInstaller & """", 1, True
                fso.DeleteFile gitInstaller
            Else
                MsgBox "Failed to download Git. Please install manually from git-scm.com", vbCritical, "Error"
                WScript.Quit
            End If
        End If

        MsgBox "Dependencies installed!" & vbCrLf & vbCrLf & _
               "Please RESTART this installer to continue with ReelRecon setup.", vbInformation, "ReelRecon Installer"
        WScript.Quit
    End If

    ' Dependencies are installed - run the Python installer GUI
    scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
    installerPath = scriptPath & "\lib\ReelRecon-Installer.pyw"

    ' Find pythonw.exe
    pythonwPath = ""
    If fso.FileExists("C:\Python312\pythonw.exe") Then
        pythonwPath = "C:\Python312\pythonw.exe"
    ElseIf fso.FileExists("C:\Python311\pythonw.exe") Then
        pythonwPath = "C:\Python311\pythonw.exe"
    ElseIf fso.FileExists("C:\Python310\pythonw.exe") Then
        pythonwPath = "C:\Python310\pythonw.exe"
    Else
        ' Try Windows Store Python or PATH
        Set objExec = WshShell.Exec("where pythonw.exe")
        pythonwPath = Trim(objExec.StdOut.ReadLine())
    End If

    If pythonwPath = "" Or Not fso.FileExists(pythonwPath) Then
        ' Fallback to python.exe with windowstyle hidden
        Set objExec = WshShell.Exec("where python.exe")
        pythonPath = Trim(objExec.StdOut.ReadLine())
        If pythonPath <> "" Then
            WshShell.Run """" & pythonPath & """ """ & installerPath & """", 0, False
        Else
            MsgBox "Python not found in PATH. Please restart your computer and try again.", vbCritical, "Error"
        End If
    Else
        WshShell.Run """" & pythonwPath & """ """ & installerPath & """", 0, False
    End If
End Sub

' Run main
Main()
