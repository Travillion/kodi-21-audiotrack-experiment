#!/usr/bin/env python3
"""Apply the comprehensive Kodi 21.2 EDL AudioTrack mute experiment.

CUT edits retain their normal packet-drop behavior. EDL MUTE edits keep audio
packets flowing and ask ActiveAE/Android AudioTrack to mute output, testing the
integrated behavior on an actual Android passthrough playback path.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "kodi"

def replace_once(path, old, new, label):
    p = ROOT / path
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match in {path}, found {count}")
    p.write_text(text.replace(old, new, 1))
    print(f"Patched {label}: {path}")

# VideoPlayer: represent EDL MUTE as an output mute, not dropped encoded packets.
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayer.h",
    '  void ProcessAudioData(CDemuxStream* pStream, DemuxPacket* pPacket);\n',
    '  void ProcessAudioData(CDemuxStream* pStream, DemuxPacket* pPacket);\n'
    '  void SetEDLMute(bool enabled);\n',
    "EDL mute helper declaration",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayer.h",
    '  CEdl m_Edl;\n  bool m_SkipCommercials;\n',
    '  CEdl m_Edl;\n'
    '  bool m_edlMuteActive{false};\n'
    '  bool m_edlMutePreviousState{false};\n'
    '  bool m_SkipCommercials;\n',
    "EDL mute state",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayer.cpp",
    '#include "cores/EdlEdit.h"\n',
    '#include "cores/EdlEdit.h"\n#include "cores/AudioEngine/Interfaces/AE.h"\n',
    "ActiveAE interface include",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayer.cpp",
    '  CLog::Log(LOGINFO, "CVideoPlayer::CloseFile()");\n',
    '  CLog::Log(LOGINFO, "CVideoPlayer::CloseFile()");\n'
    '  SetEDLMute(false); // Never leave audio muted when playback closes.\n',
    "restore mute on close",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayer.cpp",
    'void CVideoPlayer::ProcessAudioData(CDemuxStream* pStream, DemuxPacket* pPacket)\n{\n',
    'void CVideoPlayer::SetEDLMute(bool enabled)\n'
    '{\n'
    '  if (enabled == m_edlMuteActive)\n'
    '    return;\n'
    '\n'
    '  IAE* activeAE = CServiceBroker::GetActiveAE();\n'
    '  if (!activeAE)\n'
    '    return;\n'
    '\n'
    '  if (enabled)\n'
    '  {\n'
    '    m_edlMutePreviousState = activeAE->IsMuted();\n'
    '    activeAE->SetMute(true);\n'
    '  }\n'
    '  else\n'
    '    activeAE->SetMute(m_edlMutePreviousState);\n'
    '\n'
    '  m_edlMuteActive = enabled;\n'
    '  CLog::Log(LOGINFO, "EDL AudioTrack mute experiment: {}", enabled ? "mute" : "restore");\n'
    '}\n'
    '\n'
    'void CVideoPlayer::ProcessAudioData(CDemuxStream* pStream, DemuxPacket* pPacket)\n{\n',
    "EDL mute helper implementation",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayer.cpp",
    '  EDL::Edit edit;\n'
    '  if (CheckSceneSkip(m_CurrentAudio))\n'
    '    drop = true;\n'
    '  else if (m_Edl.InEdit(DVD_TIME_TO_MSEC(m_CurrentAudio.dts + m_offset_pts), &edit) &&\n'
    '           edit.action == EDL::Action::MUTE)\n'
    '  {\n'
    '    drop = true;\n'
    '  }\n',
    '  EDL::Edit edit;\n'
    '  const bool inEdlMute =\n'
    '      m_Edl.InEdit(DVD_TIME_TO_MSEC(m_CurrentAudio.dts + m_offset_pts), &edit) &&\n'
    '      edit.action == EDL::Action::MUTE;\n'
    '  SetEDLMute(inEdlMute);\n'
    '\n'
    '  // CUT edits still drop packets; MUTE edits keep packets flowing to preserve\n'
    '  // encoded IEC61937 framing and let the AudioTrack output layer mute them.\n'
    '  if (CheckSceneSkip(m_CurrentAudio))\n'
    '    drop = true;\n',
    "keep packets flowing during EDL MUTE",
)

# Android AudioTrack: expose hardware/framework volume on the sink.
replace_once(
    "xbmc/cores/AudioEngine/Sinks/AESinkAUDIOTRACK.h",
    '  void Drain() override;\n',
    '  void Drain() override;\n'
    '  bool HasVolume() override { return m_passthrough; }\n'
    '  void SetVolume(float volume) override;\n',
    "AudioTrack sink volume interface",
)
replace_once(
    "xbmc/cores/AudioEngine/Sinks/AESinkAUDIOTRACK.h",
    '  bool               m_passthrough;\n',
    '  bool               m_passthrough;\n'
    '  float              m_volume{1.0f};\n',
    "AudioTrack sink volume state",
)
replace_once(
    "xbmc/cores/AudioEngine/Sinks/AESinkAUDIOTRACK.cpp",
    '#include <androidjni/AudioFormat.h>\n',
    '#include <androidjni/AudioFormat.h>\n#include <androidjni/JNIThreading.h>\n#include <jni.h>\n',
    "JNI includes",
)
replace_once(
    "xbmc/cores/AudioEngine/Sinks/AESinkAUDIOTRACK.cpp",
    'void CAESinkAUDIOTRACK::Deinitialize()\n{\n',
    'void CAESinkAUDIOTRACK::SetVolume(float volume)\n'
    '{\n'
    '  m_volume = std::clamp(volume, 0.0f, 1.0f);\n'
    '  if (!m_at_jni)\n'
    '    return;\n'
    '\n'
    '  // AudioTrack.setVolume(float) is the experimental mute path for encoded\n'
    '  // IEC61937. Unlike packet dropping, it does not interrupt the bitstream.\n'
    '  JNIEnv* env = xbmc_jnienv();\n'
    '  jobject track = m_at_jni->get_raw();\n'
    '  jclass trackClass = env->GetObjectClass(track);\n'
    '  if (!trackClass)\n'
    '  {\n'
    '    if (env->ExceptionCheck())\n'
    '      env->ExceptionClear();\n'
    '    CLog::Log(LOGERROR, "AudioTrack mute experiment: cannot get AudioTrack class");\n'
    '    return;\n'
    '  }\n'
    '  jmethodID setVolume = env->GetMethodID(trackClass, "setVolume", "(F)V");\n'
    '  if (setVolume)\n'
    '  {\n'
    '    jvalue args[1];\n'
    '    args[0].f = static_cast<jfloat>(m_volume);\n'
    '    env->CallVoidMethodA(track, setVolume, args);\n'
    '  }\n'
    '  if (env->ExceptionCheck())\n'
    '  {\n'
    '    CLog::Log(LOGERROR, "AudioTrack mute experiment: setVolume failed");\n'
    '    env->ExceptionClear();\n'
    '  }\n'
    '  env->DeleteLocalRef(trackClass);\n'
    '}\n'
    '\n'
    'void CAESinkAUDIOTRACK::Deinitialize()\n{\n',
    "AudioTrack Java volume call",
)
replace_once(
    "xbmc/cores/AudioEngine/Sinks/AESinkAUDIOTRACK.cpp",
    '  const char* method = m_passthrough ? (m_info.m_wantsIECPassthrough ? "IEC (PT)" : "RAW (PT)") : "PCM";\n',
    '  SetVolume(m_volume);\n'
    '  const char* method = m_passthrough ? (m_info.m_wantsIECPassthrough ? "IEC (PT)" : "RAW (PT)") : "PCM";\n',
    "initialize AudioTrack volume",
)

# Forward ActiveAE mute/volume changes to sinks that support native volume.
replace_once(
    "xbmc/cores/AudioEngine/Engines/ActiveAE/ActiveAE.cpp",
    '          if (m_sinkHasVolume)\n'
    '            m_sink.m_controlPort.SendOutMessage(CSinkControlProtocol::VOLUME, &m_volume, sizeof(float));\n',
    '          if (m_sinkHasVolume)\n'
    '          {\n'
    '            const float sinkVolume = m_muted ? 0.0f : m_volume;\n'
    '            m_sink.m_controlPort.SendOutMessage(CSinkControlProtocol::VOLUME, &sinkVolume, sizeof(float));\n'
    '          }\n',
    "preserve mute state on volume changes",
)
replace_once(
    "xbmc/cores/AudioEngine/Engines/ActiveAE/ActiveAE.cpp",
    '        case CActiveAEControlProtocol::MUTE:\n'
    '          m_muted = *(bool*)msg->data;\n'
    '          return;\n',
    '        case CActiveAEControlProtocol::MUTE:\n'
    '          m_muted = *(bool*)msg->data;\n'
    '          if (m_sinkHasVolume)\n'
    '          {\n'
    '            const float sinkVolume = m_muted ? 0.0f : m_volume;\n'
    '            m_sink.m_controlPort.SendOutMessage(CSinkControlProtocol::VOLUME, &sinkVolume, sizeof(float));\n'
    '          }\n'
    '          return;\n',
    "forward mute to native-volume sink",
)

print("EDL AudioTrack mute experiment patch applied.")
