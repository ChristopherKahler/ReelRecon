' ReelRecon Self-Bootstrapping Installer for Windows
' Downloads Git and Python if needed, then installs ReelRecon
' Continues automatically after installing dependencies (no restart required)

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' URLs for installers
pythonUrl = "https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe"
gitUrl = "https://github.com/git-for-windows/git/releases/download/v2.43.0.windows.1/Git-2.43.0-64-bit.exe"

' Temp folder for downloads
tempFolder = WshShell.ExpandEnvironmentStrings("%TEMP%")
userProfile = WshShell.ExpandEnvironmentStrings("%USERPROFILE%")

' Function to check if command exists in PATH
Function CommandExists(cmd)
    On Error Resume Next
    Set objExec = WshShell.Exec("where " & cmd)
    result = objExec.StdOut.ReadAll()
    CommandExists = (Len(Trim(result)) > 0)
    On Error Goto 0
End Function

' Function to find Python at known locations (doesn't rely on PATH)
Function FindPythonPath()
    Dim paths, path, i
    FindPythonPath = ""

    ' Common Python install locations (check newest versions first)
    paths = Array( _
        "C:\Python312\pythonw.exe", _
        "C:\Python311\pythonw.exe", _
        "C:\Python310\pythonw.exe", _
        userProfile & "\AppData\Local\Programs\Python\Python312\pythonw.exe", _
        userProfile & "\AppData\Local\Programs\Python\Python311\pythonw.exe", _
        userProfile & "\AppData\Local\Programs\Python\Python310\pythonw.exe", _
        "C:\Program Files\Python312\pythonw.exe", _
        "C:\Program Files\Python311\pythonw.exe", _
        "C:\Program Files (x86)\Python312\pythonw.exe" _
    )

    For i = 0 To UBound(paths)
        If fso.FileExists(paths(i)) Then
            FindPythonPath = paths(i)
            Exit Function
        End If
    Next

    ' Fallback: try PATH (may work if user added to PATH during install)
    On Error Resume Next
    Set objExec = WshShell.Exec("where pythonw.exe")
    result = Trim(objExec.StdOut.ReadLine())
    If fso.FileExists(result) Then
        FindPythonPath = result
    End If
    On Error Goto 0
End Function

' Function to find python.exe (fallback if pythonw not found)
Function FindPythonExePath()
    Dim paths, path, i
    FindPythonExePath = ""

    paths = Array( _
        "C:\Python312\python.exe", _
        "C:\Python311\python.exe", _
        "C:\Python310\python.exe", _
        userProfile & "\AppData\Local\Programs\Python\Python312\python.exe", _
        userProfile & "\AppData\Local\Programs\Python\Python311\python.exe", _
        userProfile & "\AppData\Local\Programs\Python\Python310\python.exe", _
        "C:\Program Files\Python312\python.exe", _
        "C:\Program Files\Python311\python.exe" _
    )

    For i = 0 To UBound(paths)
        If fso.FileExists(paths(i)) Then
            FindPythonExePath = paths(i)
            Exit Function
        End If
    Next

    On Error Resume Next
    Set objExec = WshShell.Exec("where python.exe")
    result = Trim(objExec.StdOut.ReadLine())
    If fso.FileExists(result) Then
        FindPythonExePath = result
    End If
    On Error Goto 0
End Function

' Function to find Git at known locations
Function FindGitPath()
    Dim paths, i
    FindGitPath = ""

    paths = Array( _
        "C:\Program Files\Git\cmd\git.exe", _
        "C:\Program Files (x86)\Git\cmd\git.exe", _
        userProfile & "\AppData\Local\Programs\Git\cmd\git.exe" _
    )

    For i = 0 To UBound(paths)
        If fso.FileExists(paths(i)) Then
            FindGitPath = paths(i)
            Exit Function
        End If
    Next

    On Error Resume Next
    Set objExec = WshShell.Exec("where git.exe")
    result = Trim(objExec.StdOut.ReadLine())
    If fso.FileExists(result) Then
        FindGitPath = result
    End If
    On Error Goto 0
End Function

' Function to download file using PowerShell
Sub DownloadFile(url, destination)
    psCommand = "powershell -Command ""[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '" & url & "' -OutFile '" & destination & "'"""
    WshShell.Run psCommand, 0, True
End Sub

' Function to launch the GUI installer
Sub LaunchGUIInstaller()
    scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
    installerPath = scriptPath & "\lib\ReelRecon-Installer.pyw"

    ' Find Python using absolute paths
    pythonwPath = FindPythonPath()

    If pythonwPath <> "" And fso.FileExists(pythonwPath) Then
        WshShell.Run """" & pythonwPath & """ """ & installerPath & """", 0, False
    Else
        ' Fallback to python.exe
        pythonPath = FindPythonExePath()
        If pythonPath <> "" And fso.FileExists(pythonPath) Then
            WshShell.Run """" & pythonPath & """ """ & installerPath & """", 0, False
        Else
            MsgBox "Python installation could not be found." & vbCrLf & vbCrLf & _
                   "Please restart your computer to update PATH, then run this installer again.", vbCritical, "Error"
        End If
    End If
End Sub

' Main installation logic
Sub Main()
    Dim needsPython, needsGit
    Dim installedPython, installedGit
    needsPython = False
    needsGit = False
    installedPython = False
    installedGit = False

    ' Check for Python (first by known paths, then by PATH)
    If FindPythonPath() = "" And FindPythonExePath() = "" Then
        If Not CommandExists("python") Then
            needsPython = True
        End If
    End If

    ' Check for Git (first by known paths, then by PATH)
    If FindGitPath() = "" Then
        If Not CommandExists("git") Then
            needsGit = True
        End If
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
                installedPython = True
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
                installedGit = True
            Else
                MsgBox "Failed to download Git. Please install manually from git-scm.com", vbCritical, "Error"
                WScript.Quit
            End If
        End If

        ' Verify installations succeeded by checking known paths
        If installedPython Then
            WScript.Sleep 1000  ' Brief pause for filesystem
            If FindPythonPath() = "" And FindPythonExePath() = "" Then
                MsgBox "Python installation could not be verified." & vbCrLf & vbCrLf & _
                       "Please restart your computer and run this installer again.", vbCritical, "Error"
                WScript.Quit
            End If
        End If

        If installedGit Then
            WScript.Sleep 1000
            If FindGitPath() = "" Then
                MsgBox "Git installation could not be verified." & vbCrLf & vbCrLf & _
                       "Please restart your computer and run this installer again.", vbCritical, "Error"
                WScript.Quit
            End If
        End If

        ' Show success message and continue automatically
        MsgBox "Dependencies installed successfully!" & vbCrLf & vbCrLf & _
               "Continuing with ReelRecon setup...", vbInformation, "ReelRecon Installer"
    End If

    ' Launch the GUI installer (continues automatically after deps install)
    LaunchGUIInstaller
End Sub

' Run main
Main()
