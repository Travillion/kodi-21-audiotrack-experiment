# Technical findings: Kodi 21 AudioTrack EDL mute experiment

## Baseline

- Target Kodi source: `xbmc/xbmc`, branch/tag `21.2-Omega`.
- Relevant sink: `xbmc/cores/AudioEngine/Sinks/AESinkAUDIOTRACK.cpp`.
- Relevant EDL packet handling: `xbmc/cores/VideoPlayer/VideoPlayer.cpp`, in the audio demux packet path.
- Android JNI dependency pinned by Kodi 21.2: `xbmc/libandroidjni`, revision `7c1f1b326c14e0cf4d646b63a2ac448d7a8debe0`.

## Confirmed source observations

1. The EDL MUTE branch in `CVideoPlayer` marks audio packets as dropped while the current packet timestamp is inside an EDL MUTE edit. This does not preserve a continuous encoded bitstream.
2. The Android AudioTrack sink writes IEC61937 data through `CJNIAudioTrack::write`. The sink's current JNI wrapper exposes playback, write, timestamp, state, and buffer methods, but does **not** expose `AudioTrack.setVolume(float)`.
3. The JNI wrapper is a separate dependency (`xbmc/libandroidjni`), not source code contained in the main Kodi repository. A proper test that calls Android AudioTrack volume therefore needs a change to that dependency as well as the Kodi sink.
4. Kodi's ActiveAE mute path deamplifies PCM samples. That is not evidence that Android's AudioTrack gain controls encoded IEC passthrough; this must be tested on the Shield/AVR.

## Experimental question

Can calling Android `AudioTrack.setVolume(0.0f)` on Kodi's active IEC61937 AudioTrack silence TrueHD passthrough while Kodi continues writing the encoded stream, and then restore audio with `setVolume(1.0f)` without losing the AVR's TrueHD/Atmos indication or causing a discontinuity?

## Required pass/fail checks

- TrueHD/Atmos output becomes silent during the test mute interval.
- AVR continues to report the same TrueHD/Atmos input format during mute; it must not fall back to PCM or lose/reacquire the format.
- Audio returns promptly and cleanly after unmute.
- No playback stall, audible burst, or persistent sync change.
- AC3/E-AC3 and ordinary PCM playback remain unaffected.

## Guardrails

- Keep the experiment in this private repository and based on Kodi 21.2 Omega.
- Do not change the user's installed Kodi or the main EDL behavior until the test has been built and its result is known.
- Do not claim AudioTrack volume works for passthrough based only on Android API documentation.
- The Android build must be reproducible and produce a signed APK artifact suitable for manual installation on an NVIDIA Shield TV. Verify the build workflow and toolchain before promising an APK.
