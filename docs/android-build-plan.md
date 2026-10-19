# Android build feasibility and next-step plan

## Why build validation comes before the code patch

Kodi's Android build is not a standalone Gradle app build. The Kodi 21.2 Omega Android guide requires the unified `tools/depends` cross-build, Android SDK/NDK setup, binary add-on build, Kodi CMake build, and APK packaging. The documented/recommended NDK is r21e (21.4.7075529), with Android SDK platform 34 and build-tools 33.0.1 in the guide.

Reference: https://github.com/xbmc/xbmc/blob/21.2-Omega/docs/README.Android.md

A GitHub Actions workflow should not be treated as proven until it completes a clean build and leaves a downloadable APK artifact. The full build may exceed ordinary hosted-runner time or disk limits; determine this with a build-only spike before investing in the experimental patch.

## Proposed sequence

1. **Build-only spike:** create a workflow that checks out Kodi 21.2 Omega, configures the documented Android toolchain for `aarch64-linux-android` (the Shield target), builds dependencies and Kodi, packages the APK, and uploads the result as an artifact. No source patches yet.
2. **Record outcome:** note runner image, tool versions, duration, disk use, and any build failures. If the hosted runner cannot complete the build reliably, stop and evaluate a more suitable hosted runner rather than asking the user to build locally.
3. **Add isolated AudioTrack test:** add `CJNIAudioTrack.setVolume(float)` to the pinned `libandroidjni` dependency and create a temporary test-only path to toggle gain on the active IEC AudioTrack. Keep the current EDL packet-drop behavior unchanged until the test control is verified.
4. **Build patched APK:** apply the patch reproducibly during CI, build and upload the APK, and retain the exact commit and logs alongside the artifact.
5. **Shield/AVR validation:** test TrueHD/Atmos continuity and silence, clean restoration, and PCM/AC3/E-AC3 regression behavior before considering any EDL logic change.

## Safety and scope

- Keep all changes in this private experiment repository.
- Do not install over the user's existing Kodi installation; use a separate package/application identity if the build supports it cleanly, or otherwise document the safe install/backup path before installation.
- Do not claim passthrough gain works until confirmed on the Shield and AVR.
- Do not commit signing secrets. A debug-signed APK is sufficient for manual test installation; signing configuration must be reproducible without exposing credentials.
