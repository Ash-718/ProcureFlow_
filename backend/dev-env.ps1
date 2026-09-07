# Dot-source this before running any `mvn` command for this project:
#   . .\backend\dev-env.ps1
#
# Why: this machine's default JDK is 25, and Lombok 1.18.38 (the latest release as
# of this build) does not yet support annotation processing under JDK 25 -- it
# silently no-ops instead of generating getters/setters/constructors, which then
# fails compilation with confusing "cannot find symbol" errors. A portable JDK 21
# (Temurin, LTS, Lombok's best-supported target) is unzipped under ..\.tools for
# exactly this reason. This has no effect on the *runtime* target -- the app still
# compiles down to bytecode compatible with release 21 either way (see pom.xml).
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:JAVA_HOME = Join-Path $ScriptDir "..\.tools\jdk-21.0.12.1+1"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
Write-Host "JAVA_HOME set to $env:JAVA_HOME"
& java -version
