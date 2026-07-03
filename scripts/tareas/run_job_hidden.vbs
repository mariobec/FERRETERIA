' Ejecuta un .bat del repo sin mostrar ventana de consola (tareas programadas).
Option Explicit

Dim fso, repoRoot, batRel, batPath, shell
Set fso = CreateObject("Scripting.FileSystemObject")
repoRoot = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))

If WScript.Arguments.Count < 1 Then
    WScript.Quit 1
End If

batRel = WScript.Arguments(0)
batPath = fso.BuildPath(repoRoot, batRel)

If Not fso.FileExists(batPath) Then
    WScript.Quit 1
End If

Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = repoRoot
shell.Run "cmd.exe /c """ & batPath & """", 0, False
