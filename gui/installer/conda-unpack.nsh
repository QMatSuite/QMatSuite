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

  ; ── Stage bundled QE engine to AppData (full variant only) ──
  ; The engines/ directory only exists in the full installer.
  ; Staging copies them to %LOCALAPPDATA%\QMatSuite\ where the
  ; engine registry (_scan_bundled) and pseudo library walk expect them.
  ; Uses xcopy /E /I /Y for robust recursive copy (handles nested subdirs).

  ${If} ${FileExists} "$INSTDIR\resources\engines\qe\bundled-7.5\bin\pw.exe"
    DetailPrint "Staging bundled QE engine to AppData..."
    nsExec::ExecToLog 'xcopy "$INSTDIR\resources\engines\qe\bundled-7.5" "$LOCALAPPDATA\QMatSuite\engines\qe\bundled-7.5" /E /I /Y /Q'
    Pop $0
    ${If} $0 == "0"
      DetailPrint "QE engine staged to AppData"
    ${Else}
      DetailPrint "Warning: QE staging returned $0"
    ${EndIf}
  ${EndIf}

  ; ── Stage bundled SSSP pseudo library to AppData (full variant only) ──
  ; Three-level layout: libraries/pseudo/SSSP/efficiency/1.3.0/
  ; Uses xcopy /E /I /Y for robust recursive copy.

  ${If} ${FileExists} "$INSTDIR\resources\libraries\pseudo\SSSP\efficiency\1.3.0\head.json"
    DetailPrint "Staging bundled SSSP pseudopotentials to AppData..."
    nsExec::ExecToLog 'xcopy "$INSTDIR\resources\libraries\pseudo\SSSP\efficiency\1.3.0" "$LOCALAPPDATA\QMatSuite\libraries\pseudo\SSSP\efficiency\1.3.0" /E /I /Y /Q'
    Pop $0
    ${If} $0 == "0"
      DetailPrint "SSSP library staged to AppData"
    ${Else}
      DetailPrint "Warning: SSSP staging returned $0"
    ${EndIf}
  ${EndIf}
!macroend
