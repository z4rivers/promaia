Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.Run chr(34) & scriptDir & "\start_promaia.bat" & Chr(34) & " hidden", 0
Set WshShell = Nothing
