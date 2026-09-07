#!/usr/bin/env bash
# Source this before running any `mvn` command for this project:
#   source backend/dev-env.sh
#
# Why: this machine's default JDK is 25, and Lombok 1.18.38 (the latest release as
# of this build) does not yet support annotation processing under JDK 25 — it
# silently no-ops instead of generating getters/setters/constructors, which then
# fails compilation with confusing "cannot find symbol" errors. A portable JDK 21
# (Temurin, LTS, Lombok's best-supported target) is unzipped under ../.tools for
# exactly this reason. This has no effect on the *runtime* target — the app still
# compiles down to bytecode compatible with release 21 either way (see pom.xml).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export JAVA_HOME="$SCRIPT_DIR/../.tools/jdk-21.0.12.1+1"
export PATH="$JAVA_HOME/bin:$PATH"
echo "JAVA_HOME set to $JAVA_HOME"
java -version
