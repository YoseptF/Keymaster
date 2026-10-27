Unicode true
Target amd64-unicode
ManifestDPIAware true
SetCompressor /SOLID lzma

!include "${KM_DEFINES}"
!include MUI2.nsh
!include LogicLib.nsh
!include FileFunc.nsh
!include WordFunc.nsh
!include Sections.nsh

!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Keymaster"
!define STATE_KEY "Software\Keymaster"
!define CEP_DIR "$APPDATA\Adobe\CEP\extensions\com.keymaster.adobe"
!define POWERSHELL "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe"

Name "Keymaster"
OutFile "${KM_OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\Keymaster"
InstallDirRegKey HKCU "${STATE_KEY}" "InstallDir"
RequestExecutionLevel user
ShowInstDetails show
ShowUninstDetails show
BrandingText "Keymaster ${KM_VERSION}"
VIProductVersion "${KM_VERSION_NUMERIC}"
VIAddVersionKey /LANG=0 "ProductName" "Keymaster"
VIAddVersionKey /LANG=0 "FileDescription" "Keymaster"
VIAddVersionKey /LANG=0 "FileVersion" "${KM_VERSION}"
VIAddVersionKey /LANG=0 "ProductVersion" "${KM_VERSION}"
VIAddVersionKey /LANG=0 "LegalCopyright" "GPL-3.0-or-later"

Var KmLang
Var SkipCore
Var Blenders
Var DoctorOk
Var FinishText
Var OfxDir

!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "$(installer.welcome.title)"
!define MUI_WELCOMEPAGE_TEXT "$(installer.welcome.text)"
!insertmacro MUI_PAGE_WELCOME
!define MUI_COMPONENTSPAGE_SMALLDESC
!define MUI_COMPONENTSPAGE_TEXT_TOP "$(installer.components.text)"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_TITLE "$(installer.finish.title)"
!define MUI_FINISHPAGE_TEXT "$FinishText"
!insertmacro MUI_PAGE_FINISH
!define MUI_UNCONFIRMPAGE_TEXT_TOP "$(installer.uninstall.text)"
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "SpanishInternational"
!include "${KM_GENERATED}/lang.nsh"

!macro KM_LANGUAGE_FUNCTION PREFIX
Function ${PREFIX}DetectLanguage
  StrCpy $KmLang ""
  ReadEnvStr $0 KEYMASTER_LANGUAGE
  ${If} $0 == "en"
  ${OrIf} $0 == "es-419"
    StrCpy $KmLang $0
  ${EndIf}
  ${If} $KmLang == ""
    ReadEnvStr $1 KEYMASTER_SETTINGS
    ${If} $1 == ""
      StrCpy $1 "$APPDATA\Keymaster\settings.json"
    ${EndIf}
    ClearErrors
    FileOpen $2 $1 r
    ${IfNot} ${Errors}
      ${Do}
        ClearErrors
        FileRead $2 $3
        ${If} ${Errors}
          ${Break}
        ${EndIf}
        ClearErrors
        ${WordFind} $3 '"language": "' "E+1}" $4
        ${IfNot} ${Errors}
          StrCpy $5 $4 6
          StrCpy $6 $4 3
          ${If} $5 == "es-419"
            StrCpy $KmLang "es-419"
          ${ElseIf} $6 == 'en"'
            StrCpy $KmLang "en"
          ${EndIf}
        ${EndIf}
      ${Loop}
      FileClose $2
    ${EndIf}
  ${EndIf}
  ${If} $KmLang == ""
    System::Call 'kernel32::GetUserDefaultUILanguage() i .r0'
    IntOp $0 $0 & 0x3FF
    ${If} $0 = 10
      StrCpy $KmLang "es-419"
    ${Else}
      StrCpy $KmLang "en"
    ${EndIf}
  ${EndIf}
  ${If} $KmLang == "es-419"
    StrCpy $LANGUAGE ${LANG_SPANISHINTERNATIONAL}
  ${Else}
    StrCpy $LANGUAGE ${LANG_ENGLISH}
  ${EndIf}
FunctionEnd
!macroend
!insertmacro KM_LANGUAGE_FUNCTION ""
!insertmacro KM_LANGUAGE_FUNCTION "un."

!macro KM_STEP ACTION
  nsExec::ExecToLog '"${POWERSHELL}" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$INSTDIR\installer\core-step.ps1" -Action ${ACTION} -InstallDir "$INSTDIR" -FfmpegUrl "${KM_FFMPEG_URL}" -FfmpegSha256 "${KM_FFMPEG_SHA256}"'
  Pop $0
!macroend

!macro KM_FAIL TEXT
  DetailPrint "${TEXT}"
  ${IfNot} ${Silent}
    MessageBox MB_OK|MB_ICONSTOP "${TEXT}"
  ${EndIf}
  SetErrorLevel 1
  Abort
!macroend

!macro KM_DEBUG_MODE VERSION
  ReadRegStr $0 HKCU "Software\Adobe\CSXS.${VERSION}" "PlayerDebugMode"
  ${If} $0 == ""
    ReadRegStr $1 HKCU "${STATE_KEY}" "PreviousDebugMode${VERSION}"
    ${If} $1 == ""
      WriteRegStr HKCU "${STATE_KEY}" "PreviousDebugMode${VERSION}" "none"
    ${EndIf}
  ${ElseIf} $0 != "1"
    WriteRegStr HKCU "${STATE_KEY}" "PreviousDebugMode${VERSION}" $0
  ${EndIf}
  WriteRegStr HKCU "Software\Adobe\CSXS.${VERSION}" "PlayerDebugMode" "1"
!macroend

!macro KM_RESTORE_DEBUG_MODE VERSION
  ReadRegStr $0 HKCU "${STATE_KEY}" "PreviousDebugMode${VERSION}"
  ${If} $0 == "none"
    DeleteRegValue HKCU "Software\Adobe\CSXS.${VERSION}" "PlayerDebugMode"
    DeleteRegKey /ifempty HKCU "Software\Adobe\CSXS.${VERSION}"
  ${ElseIf} $0 != ""
    WriteRegStr HKCU "Software\Adobe\CSXS.${VERSION}" "PlayerDebugMode" $0
  ${EndIf}
!macroend

Section "!$(installer.component.core)" SecCore
  SectionIn RO
  SetOutPath "$INSTDIR"
  WriteUninstaller "$INSTDIR\uninstall.exe"
  WriteRegStr HKCU "${STATE_KEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "Keymaster"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${KM_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "Keymaster"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "URLInfoAbout" "https://github.com/YoseptF/Keymaster"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\uninstall.exe"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\uninstall.exe" /S'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1

  DetailPrint "$(installer.step.files)"
  SetOutPath "$INSTDIR\core"
  File /r "${KM_STAGE}/core/*"
  SetOutPath "$INSTDIR\wheels"
  File /r "${KM_STAGE}/wheels/*"
  SetOutPath "$INSTDIR\bin"
  File "${KM_STAGE}/bin/uv.exe"
  SetOutPath "$INSTDIR\installer"
  File "${KM_STAGE}/core-step.ps1"
  CreateDirectory "$INSTDIR\logs"

  ReadEnvStr $1 KEYMASTER_SETTINGS
  ${If} $1 == ""
    StrCpy $1 "$APPDATA\Keymaster\settings.json"
  ${EndIf}
  ${IfNot} ${FileExists} $1
    ${GetParent} $1 $2
    CreateDirectory $2
    ${WordReplace} "$INSTDIR\core" "\" "\\" "+" $3
    ClearErrors
    FileOpen $4 $1 w
    ${IfNot} ${Errors}
      FileWrite $4 '{$\r$\n  "python": "$3\\.venv\\Scripts\\python.exe",$\r$\n  "core": "$3"$\r$\n}$\r$\n'
      FileClose $4
      WriteRegStr HKCU "${STATE_KEY}" "SettingsCreated" $1
    ${EndIf}
  ${EndIf}

  ${If} $SkipCore == 1
    DetailPrint "$(installer.mode.skip_core)"
  ${Else}
    DetailPrint "$(installer.step.ffmpeg)"
    !insertmacro KM_STEP "ffmpeg"
    ${If} $0 == 3
      !insertmacro KM_FAIL "$(installer.error.checksum)"
    ${ElseIf} $0 != 0
      !insertmacro KM_FAIL "$(installer.error.download)"
    ${EndIf}
    DetailPrint "$(installer.step.core)"
    !insertmacro KM_STEP "core"
    ${If} $0 != 0
      ${WordReplace} "$(installer.error.core)" "{log}" "$INSTDIR\logs\install.log" "+" $1
      !insertmacro KM_FAIL "$1"
    ${EndIf}
    DetailPrint "$(installer.step.settings)"
    !insertmacro KM_STEP "settings"
    ${If} $0 != 0
      ${WordReplace} "$(installer.error.core)" "{log}" "$INSTDIR\logs\install.log" "+" $1
      !insertmacro KM_FAIL "$1"
    ${EndIf}
  ${EndIf}
SectionEnd

Section "$(installer.component.app)" SecApp
  DetailPrint "$(installer.step.app)"
  RMDir /r "$INSTDIR\app"
  SetOutPath "$INSTDIR\app"
  File /r "${KM_STAGE}/app/*"
  CreateShortcut "$SMPROGRAMS\Keymaster.lnk" "$INSTDIR\core\.venv\Scripts\pythonw.exe" "-m keymaster_app" "" "" SW_SHOWNORMAL "" "$(installer.component.app.desc)"
  WriteRegStr HKCU "${STATE_KEY}" "App" "1"
  ${If} $SkipCore != 1
    !insertmacro KM_STEP "app"
    ${If} $0 != 0
      ${WordReplace} "$(installer.error.app)" "{log}" "$INSTDIR\logs\install.log" "+" $1
      DetailPrint "$1"
      ${IfNot} ${Silent}
        MessageBox MB_OK|MB_ICONEXCLAMATION "$1"
      ${EndIf}
    ${EndIf}
  ${EndIf}
SectionEnd

Section "$(installer.component.blender)" SecBlender
  SetOutPath "$INSTDIR\blender"
  File "${KM_STAGE}/blender/keymaster-blender.zip"
  StrCpy $R0 1
  ${Do}
    ClearErrors
    ${WordFind} "$Blenders" "|" "E+$R0" $R1
    ${If} ${Errors}
      ${Break}
    ${EndIf}
    IntOp $R0 $R0 + 1
    ${If} $R1 == ""
      ${Continue}
    ${EndIf}
    nsExec::ExecToStack '"$R1" --version'
    Pop $0
    Pop $1
    ${WordFind} "$1" " " "+2" $2
    ${WordFind} "$2" "." "+1" $3
    ${WordFind} "$2" "." "+2" $4
    ${If} $3 < 5
      ${WordReplace} "$(installer.blender.too_old)" "{version}" "$3.$4" "+" $5
      DetailPrint "$5"
      ${Continue}
    ${EndIf}
    ${WordReplace} "$(installer.step.blender)" "{version}" "$3.$4" "+" $5
    DetailPrint "$5"
    nsExec::ExecToLog '"$R1" --command extension install-file -r user_default -e "$INSTDIR\blender\keymaster-blender.zip"'
    Pop $0
    ${If} $0 == 0
      WriteRegStr HKCU "${STATE_KEY}\Blender" "$R1" "$APPDATA\Blender Foundation\Blender\$3.$4\extensions\user_default"
    ${Else}
      ${WordReplace} "$(installer.blender.failed)" "{version}" "$3.$4" "+" $5
      DetailPrint "$5"
    ${EndIf}
  ${Loop}
SectionEnd

Section "$(installer.component.openfx)" SecOpenfx
  RMDir /r "$INSTDIR\openfx"
  SetOutPath "$INSTDIR\openfx\Keymaster.ofx.bundle"
  File /r "${KM_STAGE}/openfx/Keymaster.ofx.bundle/*"
  StrCpy $OfxDir "$COMMONFILES64\OFX\Plugins"
  ReadEnvStr $0 OFX_PLUGIN_DIR
  ${If} $0 != ""
    StrCpy $OfxDir $0
  ${EndIf}
  ${WordReplace} "$(installer.step.openfx)" "{dir}" "$OfxDir" "+" $1
  DetailPrint "$1"
  ClearErrors
  CreateDirectory "$OfxDir"
  FileOpen $2 "$OfxDir\keymaster-write-test.tmp" w
  ${If} ${Errors}
    ${WordReplace} "$(installer.openfx.needs_admin)" "{dir}" "$OfxDir" "+" $1
    DetailPrint "$1"
    ExecShellWait "runas" "$SYSDIR\cmd.exe" '/c rmdir /s /q "$OfxDir\Keymaster.ofx.bundle" & mkdir "$OfxDir" & xcopy /e /i /y /q "$INSTDIR\openfx\Keymaster.ofx.bundle" "$OfxDir\Keymaster.ofx.bundle"' SW_HIDE
  ${Else}
    FileClose $2
    Delete "$OfxDir\keymaster-write-test.tmp"
    RMDir /r "$OfxDir\Keymaster.ofx.bundle"
    CopyFiles /SILENT "$INSTDIR\openfx\Keymaster.ofx.bundle" "$OfxDir"
  ${EndIf}
  ${If} ${FileExists} "$OfxDir\Keymaster.ofx.bundle\Contents\Win64\Keymaster.ofx"
    WriteRegStr HKCU "${STATE_KEY}" "OpenFX" "$OfxDir\Keymaster.ofx.bundle"
  ${Else}
    ${WordReplace} "$(installer.openfx.failed)" "{dir}" "$OfxDir" "+" $1
    DetailPrint "$1"
    ${IfNot} ${Silent}
      MessageBox MB_OK|MB_ICONEXCLAMATION "$1"
    ${EndIf}
  ${EndIf}
SectionEnd

Section "$(installer.component.adobe)" SecAdobe
  DetailPrint "$(installer.step.adobe)"
  RMDir /r "${CEP_DIR}"
  SetOutPath "${CEP_DIR}"
  File /r "${KM_STAGE}/adobe/com.keymaster.adobe/*"
  WriteRegStr HKCU "${STATE_KEY}" "Adobe" "1"
  !insertmacro KM_DEBUG_MODE 11
  !insertmacro KM_DEBUG_MODE 12
SectionEnd

Section "-finish"
  StrCpy $DoctorOk 1
  ${If} $SkipCore != 1
    DetailPrint "$(installer.step.doctor)"
    !insertmacro KM_STEP "doctor"
    ${If} $0 != 0
      StrCpy $DoctorOk 0
    ${EndIf}
  ${EndIf}
  ${If} $DoctorOk == 1
    StrCpy $FinishText "$(installer.finish.ok)"
    DetailPrint "$(installer.done.ok)"
  ${Else}
    StrCpy $FinishText "$(installer.finish.problems)"
    DetailPrint "$(installer.finish.problems)"
  ${EndIf}
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "EstimatedSize" $0
  SetOutPath "$INSTDIR"
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecCore} "$(installer.component.core.desc)"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecApp} "$(installer.component.app.desc)"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecBlender} "$(installer.component.blender.desc)"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecOpenfx} "$(installer.component.openfx.desc)"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecAdobe} "$(installer.component.adobe.desc)"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Function AddBlender
  Exch $0
  ${If} ${FileExists} "$0"
    StrCpy $Blenders "$Blenders$0|"
  ${EndIf}
  Pop $0
FunctionEnd

Function DetectBlenders
  StrCpy $Blenders ""
  FindFirst $0 $1 "$PROGRAMFILES64\Blender Foundation\Blender*"
  ${DoWhile} $1 != ""
    ${WordFind} "$1" " " "+2" $2
    ${WordFind} "$2" "." "+1" $3
    ${If} $3 >= 5
    ${OrIf} $2 == $1
      Push "$PROGRAMFILES64\Blender Foundation\$1\blender.exe"
      Call AddBlender
    ${EndIf}
    FindNext $0 $1
  ${Loop}
  FindClose $0
  Push "$PROGRAMFILES32\Steam\steamapps\common\Blender\blender.exe"
  Call AddBlender
  Push "$PROGRAMFILES64\Steam\steamapps\common\Blender\blender.exe"
  Call AddBlender
FunctionEnd

Function FoundAny
  Exch $0
  Push $1
  Push $2
  FindFirst $1 $2 "$0"
  FindClose $1
  StrCpy $0 0
  ${If} $2 != ""
    StrCpy $0 1
  ${EndIf}
  Pop $2
  Pop $1
  Exch $0
FunctionEnd

!macro KM_NOT_FOUND SECTION TEXT
  !insertmacro UnselectSection ${SECTION}
  SectionSetText ${SECTION} "${TEXT} $(installer.component.not_found)"
!macroend

!macro KM_PICK SECTION ITEM
  ClearErrors
  ${WordFind} ",$R1," ",${ITEM}," "E+1{" $R2
  ${If} ${Errors}
    !insertmacro UnselectSection ${SECTION}
  ${Else}
    !insertmacro SelectSection ${SECTION}
  ${EndIf}
!macroend

Function .onInit
  Call DetectLanguage
  ${GetParameters} $R0
  StrCpy $SkipCore 0
  ClearErrors
  ${GetOptions} $R0 "/SKIPCORE" $R1
  ${IfNot} ${Errors}
    StrCpy $SkipCore 1
  ${EndIf}

  Call DetectBlenders
  ${If} $Blenders == ""
    !insertmacro KM_NOT_FOUND ${SecBlender} "$(installer.component.blender)"
    !insertmacro SetSectionFlag ${SecBlender} ${SF_RO}
  ${EndIf}
  Push "$PROGRAMFILES64\Blackmagic Design\DaVinci Resolve\Resolve.exe"
  Call FoundAny
  Pop $0
  Push "$PROGRAMFILES64\Nuke*"
  Call FoundAny
  Pop $1
  ${If} $0 == 0
  ${AndIf} $1 == 0
    !insertmacro KM_NOT_FOUND ${SecOpenfx} "$(installer.component.openfx)"
  ${EndIf}
  Push "$PROGRAMFILES64\Adobe\Adobe After Effects*"
  Call FoundAny
  Pop $0
  Push "$PROGRAMFILES64\Adobe\Adobe Premiere Pro*"
  Call FoundAny
  Pop $1
  ${If} $0 == 0
  ${AndIf} $1 == 0
    !insertmacro KM_NOT_FOUND ${SecAdobe} "$(installer.component.adobe)"
  ${EndIf}

  ClearErrors
  ${GetOptions} $R0 "/COMPONENTS=" $R1
  ${IfNot} ${Errors}
    !insertmacro KM_PICK ${SecApp} "app"
    !insertmacro KM_PICK ${SecOpenfx} "openfx"
    !insertmacro KM_PICK ${SecAdobe} "adobe"
    ${If} $Blenders != ""
      !insertmacro KM_PICK ${SecBlender} "blender"
    ${EndIf}
  ${EndIf}

  nsExec::ExecToStack '"$SYSDIR\nvidia-smi.exe" -L'
  Pop $0
  Pop $1
  ${If} $0 != 0
  ${AndIfNot} ${Silent}
    MessageBox MB_YESNO|MB_ICONEXCLAMATION "$(installer.gpu.missing)$\r$\n$\r$\n$(installer.prompt.continue)" IDYES gpu_continue
    Abort
  ${EndIf}
  gpu_continue:
FunctionEnd

Function un.onInit
  Call un.DetectLanguage
FunctionEnd

Section "Uninstall"
  StrCpy $R0 0
  ${Do}
    EnumRegValue $R1 HKCU "${STATE_KEY}\Blender" $R0
    ${If} $R1 == ""
      ${Break}
    ${EndIf}
    ReadRegStr $R2 HKCU "${STATE_KEY}\Blender" $R1
    ${If} ${FileExists} "$R1"
      nsExec::ExecToLog '"$R1" --command extension remove keymaster'
      Pop $0
    ${EndIf}
    RMDir /r "$R2\keymaster"
    IntOp $R0 $R0 + 1
  ${Loop}

  ReadRegStr $R1 HKCU "${STATE_KEY}" "OpenFX"
  ${If} $R1 != ""
  ${AndIf} ${FileExists} "$R1\*.*"
    RMDir /r "$R1"
    ${If} ${FileExists} "$R1\*.*"
      ExecShellWait "runas" "$SYSDIR\cmd.exe" '/c rmdir /s /q "$R1"' SW_HIDE
    ${EndIf}
  ${EndIf}

  ReadRegStr $R1 HKCU "${STATE_KEY}" "Adobe"
  ${If} $R1 == "1"
    RMDir /r "${CEP_DIR}"
  ${EndIf}
  !insertmacro KM_RESTORE_DEBUG_MODE 11
  !insertmacro KM_RESTORE_DEBUG_MODE 12

  ReadRegStr $R1 HKCU "${STATE_KEY}" "App"
  ${If} $R1 == "1"
    Delete "$SMPROGRAMS\Keymaster.lnk"
  ${EndIf}

  ReadRegStr $R1 HKCU "${STATE_KEY}" "SettingsCreated"
  ${If} $R1 != ""
    Delete "$R1"
    ${GetParent} "$R1" $R2
    RMDir "$R2"
  ${EndIf}

  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  DeleteRegKey HKCU "${STATE_KEY}"
SectionEnd
