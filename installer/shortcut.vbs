Set oWS = WScript.CreateObject("WScript.Shell")
Set oFSO = CreateObject("Scripting.FileSystemObject")

' Delete old shortcuts if they exist
Sub DeleteOld(sPath)
    On Error Resume Next
    If oFSO.FileExists(sPath) Then
        oFSO.DeleteFile sPath, True
        WScript.Echo "REMOVED_OLD: " & sPath
    End If
End Sub

DeleteOld("C:\Users\Public\Desktop\MosqueAudioGuard.lnk")
DeleteOld("C:\Users\MBadj\OneDrive\Desktop\MosqueAudioGuard.lnk")

Sub MakeShortcut(sLinkFile)
    On Error Resume Next
    Set oLink = oWS.CreateShortcut(sLinkFile)
    oLink.TargetPath = "C:\AudioGuard\dist\AudioGuard\AudioGuard.exe"
    oLink.WorkingDirectory = "C:\AudioGuard\dist\AudioGuard"
    oLink.Description = "AudioGuard - Lossless Audio Backup System"
    oLink.Save
    If Err.Number = 0 Then
        WScript.Echo "SAVED: " & sLinkFile
    Else
        WScript.Echo "ERR saving " & sLinkFile & ": " & Err.Description
    End If
End Sub

MakeShortcut("C:\Users\Public\Desktop\AudioGuard.lnk")
MakeShortcut("C:\Users\MBadj\OneDrive\Desktop\AudioGuard.lnk")
