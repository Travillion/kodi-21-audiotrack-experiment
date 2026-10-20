#!/usr/bin/env python3
"""Apply the Kodi 21.2 EDL IEC pause-burst mute experiment.

CUT edits retain normal packet-drop behavior. EDL MUTE intervals replace the
corresponding encoded IEC61937 output packets with pause bursts, preserving the
continuous passthrough carrier without relying on ineffective AudioTrack volume.
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

# Give this experimental APK a distinct Android package ID so it installs beside
# the user's existing Kodi app instead of replacing it.
replace_once(
    "version.txt",
    "APP_PACKAGE org.xbmc.kodi\n",
    "APP_PACKAGE org.xbmc.kodi.edlmute\n",
    "side-by-side Android package ID",
)

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

# Carry the decoded-frame EDL mute decision to ActiveAE as packet metadata.
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayerAudio.h",
    '#include "AudioSinkAE.h"\\n',
    '#include "AudioSinkAE.h"\\n#include "Edl.h"\\n',
    "audio player EDL include",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayerAudio.h",
    '  CVideoPlayerAudio(CDVDClock* pClock, CDVDMessageQueue& parent, CProcessInfo &processInfo);\\n',
    '  CVideoPlayerAudio(CDVDClock* pClock, CDVDMessageQueue& parent, CProcessInfo &processInfo, CEdl& edl);\\n',
    "pass EDL to audio player",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayerAudio.h",
    '  CAudioSinkAE m_audioSink; // audio output device\\n',
    '  CAudioSinkAE m_audioSink; // audio output device\\n  CEdl& m_edl; // original-media EDL timeline for per-frame mute decisions\\n',
    "audio player EDL reference",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayerAudio.cpp",
    '#include "AudioSinkAE.h"\\n',
    '#include "AudioSinkAE.h"\\n#include "cores/VideoPlayer/Edl.h"\\n',
    "audio player EDL implementation include",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayerAudio.cpp",
    'CVideoPlayerAudio::CVideoPlayerAudio(CDVDClock* pClock, CDVDMessageQueue& parent, CProcessInfo &processInfo)\\n  : CThread("VideoPlayerAudio"), m_messageParent(parent), m_audioSink(pClock)',
    'CVideoPlayerAudio::CVideoPlayerAudio(CDVDClock* pClock, CDVDMessageQueue& parent, CProcessInfo &processInfo, CEdl& edl)\\n  : CThread("VideoPlayerAudio"), m_messageParent(parent), m_audioSink(pClock), m_edl(edl)',
    "initialize audio player EDL reference",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayer.cpp",
    '  m_VideoPlayerAudio = new CVideoPlayerAudio(&m_clock, m_messenger, *m_processInfo);\\n',
    '  m_VideoPlayerAudio = new CVideoPlayerAudio(&m_clock, m_messenger, *m_processInfo, m_Edl);\\n',
    "pass EDL from video player",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayer.cpp",
    '#include "cores/AudioEngine/Interfaces/AE.h"\\n',
    '',
    "remove unused ActiveAE volume-mute include",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayer.h",
    '  void SetEDLMute(bool enabled);\\n',
    '',
    "remove ineffective global mute helper declaration",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayer.h",
    '  bool m_edlMuteActive{false};\\n  bool m_edlMutePreviousState{false};\\n',
    '',
    "remove ineffective global mute state",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayer.cpp",
    '  SetEDLMute(false); // Never leave audio muted when playback closes.\\n',
    '',
    "remove global mute restore on close",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayer.cpp",
    'void CVideoPlayer::SetEDLMute(bool enabled)\\n{\\n'
    '  if (enabled == m_edlMuteActive)\\n'
    '    return;\\n'
    '\\n'
    '  IAE* activeAE = CServiceBroker::GetActiveAE();\\n'
    '  if (!activeAE)\\n'
    '    return;\\n'
    '\\n'
    '  if (enabled)\\n'
    '  {\\n'
    '    m_edlMutePreviousState = activeAE->IsMuted();\\n'
    '    activeAE->SetMute(true);\\n'
    '  }\\n'
    '  else\\n'
    '    activeAE->SetMute(m_edlMutePreviousState);\\n'
    '\\n'
    '  m_edlMuteActive = enabled;\\n'
    '  CLog::Log(LOGINFO, "EDL AudioTrack mute experiment: {}", enabled ? "mute" : "restore");\\n'
    '}\\n'
    '\\n',
    '',
    "remove ineffective global mute helper implementation",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayer.cpp",
    '  EDL::Edit edit;\\n'
    '  const bool inEdlMute =\\n'
    '      m_Edl.InEdit(DVD_TIME_TO_MSEC(m_CurrentAudio.dts + m_offset_pts), &edit) &&\\n'
    '      edit.action == EDL::Action::MUTE;\\n'
    '  SetEDLMute(inEdlMute);\\n'
    '\\n'
    '  // CUT edits still drop packets; MUTE edits keep packets flowing to preserve\\n'
    '  // encoded IEC61937 framing and let the AudioTrack output layer mute them.\\n'
    '  if (CheckSceneSkip(m_CurrentAudio))\\n'
    '    drop = true;\\n',
    '  // EDL MUTE is handled on decoded audio frames by replacing IEC61937\\n'
    '  // payloads with pause bursts. CUT edits still drop packets as before.\\n'
    '  if (CheckSceneSkip(m_CurrentAudio))\\n'
    '    drop = true;\\n',
    "leave EDL MUTE packets flowing without global volume changes",
)
replace_once(
    "xbmc/cores/AudioEngine/Interfaces/AEStream.h",
    '    double pts = 0;\\n',
    '    double pts = 0;\\n    bool edlMute = false;\\n',
    "carry EDL mute metadata through ActiveAE",
)
replace_once(
    "xbmc/cores/VideoPlayer/AudioSinkAE.cpp",
    '      ext.pts = audioframe.pts / DVD_TIME_BASE * 1000;\\n',
    '      ext.pts = audioframe.pts / DVD_TIME_BASE * 1000;\\n',
    "preserve audio PTS (metadata is assigned below)",
)
replace_once(
    "xbmc/cores/VideoPlayer/AudioSinkAE.cpp",
    '    IAEStream::ExtData ext;\\n    if (offset == 0)\\n',
    '    IAEStream::ExtData ext;\\n'
    '    if (audioframe.pts != DVD_NOPTS_VALUE && audioframe.duration > 0)\\n'
    '    {\\n'
    '      const int64_t frameStartMs = DVD_TIME_TO_MSEC(audioframe.pts);\\n'
    '      const int64_t frameEndMs = frameStartMs + DVD_TIME_TO_MSEC(audioframe.duration);\\n'
    '      for (const auto& edit : m_edl.GetRawEditList())\\n'
    '      {\\n'
    '        if (edit.action == EDL::Action::MUTE && frameStartMs < edit.end && frameEndMs > edit.start)\\n'
    '        {\\n'
    '          ext.edlMute = true;\\n'
    '          break;\\n'
    '        }\\n'
    '      }\\n'
    '    }\\n'
    '    if (offset == 0)\\n',
    "detect decoded audio frames overlapping EDL MUTE intervals",
)
replace_once(
    "xbmc/cores/AudioEngine/Engines/ActiveAE/ActiveAEStream.cpp",
    '        m_currentBuffer->timestamp = pts;\\n',
    '        m_currentBuffer->timestamp = pts;\\n'
    '        if (m_format.m_dataFormat == AE_FMT_RAW)\\n'
    '          m_currentBuffer->pkt->pause_burst_ms =\\n'
    '              extData && extData->edlMute ? m_format.m_streamInfo.GetDuration() : 0;\\n',
    "mark raw packets for EDL pause bursts",
)
replace_once(
    "xbmc/cores/AudioEngine/Engines/ActiveAE/ActiveAESink.cpp",
    '      if (frames > 0)\\n'
    '      {\\n'
    '        m_packer->Reset();\\n'
    '        m_packer->Pack(m_sinkFormat.m_streamInfo, buffer[0], frames);\\n'
    '      }\\n'
    '      else if (samples->pkt->pause_burst_ms > 0)\\n',
    '      if (samples->pkt->pause_burst_ms > 0)\\n'
    '      {\\n'
    '        // EDL MUTE: preserve IEC61937 framing while replacing the encoded\\n'
    '        // payload with a standards-compliant pause burst.\\n'
    '        bool burst = m_extStreaming && (m_packer->GetBuffer()[0] != 0);\\n'
    '        if (!m_packer->PackPause(m_sinkFormat.m_streamInfo, samples->pkt->pause_burst_ms, burst))\\n'
    '          skipSwap = true;\\n'
    '      }\\n'
    '      else if (frames > 0)\\n'
    '      {\\n'
    '        m_packer->Reset();\\n'
    '        m_packer->Pack(m_sinkFormat.m_streamInfo, buffer[0], frames);\\n'
    '      }\\n'
    '      else if (false)\\n',
    "emit IEC pause bursts for muted raw packets",
)
print("EDL IEC pause-burst mute experiment patch applied.")
