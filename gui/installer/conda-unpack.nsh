!macro customInstall
  DetailPrint "Initializing Python runtime..."
  nsExec::ExecToLog '"$INSTDIR\resources\runtime\python.exe" "$INSTDIR\resources\runtime\Scripts\conda-unpack"'
  Pop $0
  ${If} $0 == "0"
    FileOpen $1 "$INSTDIR\resources\runtime\.conda-unpacked" w
    FileWrite $1 "installed"
    FileClose $1
    DetailPrint "Python runtime initialized successfully"
  ${Else}
    DetailPrint "Warning: conda-unpack returned $0 (runtime may still work)"
  ${EndIf}
!macroend
