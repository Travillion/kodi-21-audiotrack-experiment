#!/usr/bin/env python3
"""Apply the Kodi 21.2 EDL IEC pause-burst mute experiment for Windows.

CUT edits retain normal packet dropping. Kodi's original MUTE behavior is
preserved except for TrueHD passthrough, where IEC pause bursts keep the
receiver carrier active without relying on AudioTrack volume controls.
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


# Windows desktop Kodi does not use Android's APP_PACKAGE identifier.
# Keep the upstream Windows application identity unchanged; distribute as a
# portable test folder so its profile stays separate from regular Kodi.

# Only TrueHD passthrough bypasses Kodi's original MUTE packet dropping.
# All other codecs retain the original behavior; CUT handling is unchanged.
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
    '  if (CheckSceneSkip(m_CurrentAudio))\n'
    '    drop = true;\n'
    '  else if (m_Edl.InEdit(DVD_TIME_TO_MSEC(m_CurrentAudio.dts + m_offset_pts), &edit) &&\n'
    '           edit.action == EDL::Action::MUTE &&\n'
    '           !(m_CurrentAudio.hint.codec == AV_CODEC_ID_TRUEHD && m_VideoPlayerAudio->IsPassthrough()))\n'
    '  {\n'
    '    // Preserve Kodi\'s original mute behavior except for TrueHD passthrough.\n'
    '    // TrueHD passthrough instead uses IEC pause bursts to keep the carrier active.\n'
    '    drop = true;\n'
    '  }\n',
    "keep EDL MUTE packets flowing",
)

# Pass the original-media EDL timeline into the audio player.
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayerAudio.h",
    '#include "AudioSinkAE.h"\n',
    '#include "AudioSinkAE.h"\n#include "Edl.h"\n',
    "audio player EDL include",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayerAudio.h",
    '  CVideoPlayerAudio(CDVDClock* pClock, CDVDMessageQueue& parent, CProcessInfo &processInfo);\n',
    '  CVideoPlayerAudio(CDVDClock* pClock, CDVDMessageQueue& parent, CProcessInfo &processInfo, CEdl& edl);\n',
    "audio player constructor declaration",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayerAudio.h",
    '  CAudioSinkAE m_audioSink; // audio output device\n',
    '  CAudioSinkAE m_audioSink; // audio output device\n'
    '  CEdl& m_edl; // original-media EDL timeline\n',
    "audio player EDL reference",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayerAudio.cpp",
    'CVideoPlayerAudio::CVideoPlayerAudio(CDVDClock* pClock, CDVDMessageQueue& parent, CProcessInfo &processInfo)\n'
    ': CThread("VideoPlayerAudio"), IDVDStreamPlayerAudio(processInfo)\n'
    ', m_messageQueue("audio")\n'
    ', m_messageParent(parent)\n'
    ', m_audioSink(pClock)\n',
    'CVideoPlayerAudio::CVideoPlayerAudio(CDVDClock* pClock, CDVDMessageQueue& parent, CProcessInfo &processInfo, CEdl& edl)\n'
    ': CThread("VideoPlayerAudio"), IDVDStreamPlayerAudio(processInfo)\n'
    ', m_messageQueue("audio")\n'
    ', m_messageParent(parent)\n'
    ', m_audioSink(pClock)\n'
    ', m_edl(edl)\n',
    "audio player EDL initialization",
)
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayer.cpp",
    '  m_VideoPlayerAudio = new CVideoPlayerAudio(&m_clock, m_messenger, *m_processInfo);\n',
    '  m_VideoPlayerAudio = new CVideoPlayerAudio(&m_clock, m_messenger, *m_processInfo, m_Edl);\n',
    "pass EDL to audio player",
)

# Compute mute at decoded-frame granularity. A compressed frame overlapping an
# EDL boundary is muted as a whole because encoded payloads cannot be split.
replace_once(
    "xbmc/cores/VideoPlayer/VideoPlayerAudio.cpp",
    '  int framesOutput = m_audioSink.AddPackets(audioframe);\n',
    '  bool edlMute = false;\n'
    '  if (audioframe.pts != DVD_NOPTS_VALUE && audioframe.duration > 0)\n'
    '  {\n'
    '    const int64_t frameStartMs = DVD_TIME_TO_MSEC(audioframe.pts);\n'
    '    const int64_t frameEndMs = DVD_TIME_TO_MSEC(audioframe.pts + audioframe.duration);\n'
    '    for (const auto& edit : m_edl.GetRawEditList())\n'
    '    {\n'
    '      if (edit.action == EDL::Action::MUTE && frameStartMs < edit.end && frameEndMs > edit.start)\n'
    '      {\n'
    '        edlMute = true;\n'
    '        break;\n'
    '      }\n'
    '    }\n'
    '  }\n'
    '  int framesOutput = m_audioSink.AddPackets(audioframe, edlMute);\n',
    "detect decoded frames overlapping EDL MUTE",
)

# Extend the sink call with the frame's mute bit and pass it through ActiveAE.
replace_once(
    "xbmc/cores/VideoPlayer/AudioSinkAE.h",
    '  unsigned int AddPackets(const DVDAudioFrame &audioframe);\n',
    '  unsigned int AddPackets(const DVDAudioFrame &audioframe, bool edlMute);\n',
    "audio sink AddPackets declaration",
)
replace_once(
    "xbmc/cores/VideoPlayer/AudioSinkAE.cpp",
    'unsigned int CAudioSinkAE::AddPackets(const DVDAudioFrame &audioframe)\n',
    'unsigned int CAudioSinkAE::AddPackets(const DVDAudioFrame &audioframe, bool edlMute)\n',
    "audio sink AddPackets implementation signature",
)
replace_once(
    "xbmc/cores/VideoPlayer/AudioSinkAE.cpp",
    '    IAEStream::ExtData ext;\n'
    '    if (offset == 0)\n',
    '    IAEStream::ExtData ext;\n'
    '    ext.edlMute = edlMute;\n'
    '    if (offset == 0)\n',
    "pass EDL mute metadata into ActiveAE",
)
replace_once(
    "xbmc/cores/AudioEngine/Interfaces/AEStream.h",
    '    double pts = 0;\n',
    '    double pts = 0;\n'
    '    bool edlMute = false;\n',
    "ActiveAE stream metadata field",
)
replace_once(
    "xbmc/cores/AudioEngine/Engines/ActiveAE/ActiveAEStream.cpp",
    '        m_currentBuffer->timestamp = pts;\n',
    '        m_currentBuffer->timestamp = pts;\n'
    '        if (m_format.m_dataFormat == AE_FMT_RAW)\n'
    '          m_currentBuffer->pkt->pause_burst_ms =\n'
    '              extData && extData->edlMute ? m_format.m_streamInfo.GetDuration() : 0;\n',
    "mark raw packets for IEC pause bursts",
)

# In Kodi's IEC packer mode, prioritize the pause-burst marker even though the
# original raw packet still contains encoded frames.
replace_once(
    "xbmc/cores/AudioEngine/Engines/ActiveAE/ActiveAESink.cpp",
    '      if (frames > 0)\n'
    '      {\n'
    '        m_packer->Reset();\n'
    '        m_packer->Pack(m_sinkFormat.m_streamInfo, buffer[0], frames);\n'
    '      }\n'
    '      else if (samples->pkt->pause_burst_ms > 0)\n'
    '      {\n'
    '        // construct a pause burst if we have already output valid audio\n'
    '        bool burst = m_extStreaming && (m_packer->GetBuffer()[0] != 0);\n'
    '        if (!m_packer->PackPause(m_sinkFormat.m_streamInfo, samples->pkt->pause_burst_ms, burst))\n'
    '          skipSwap = true;\n'
    '      }\n'
    '      else\n'
    '        m_packer->Reset();\n',
    '      if (samples->pkt->pause_burst_ms > 0)\n'
    '      {\n'
    '        // Replace the encoded payload with an IEC61937 pause burst during EDL MUTE.\n'
    '        bool burst = m_extStreaming && (m_packer->GetBuffer()[0] != 0);\n'
    '        if (!m_packer->PackPause(m_sinkFormat.m_streamInfo, samples->pkt->pause_burst_ms, burst))\n'
    '          skipSwap = true;\n'
    '      }\n'
    '      else if (frames > 0)\n'
    '      {\n'
    '        m_packer->Reset();\n'
    '        m_packer->Pack(m_sinkFormat.m_streamInfo, buffer[0], frames);\n'
    '      }\n'
    '      else\n'
    '        m_packer->Reset();\n',
    "emit pause bursts instead of muted encoded packets",
)

print("EDL IEC pause-burst mute experiment patch applied.")
