# ============================================================
# Piper TTS adapter for LiveKit Agents VoicePipelineAgent
# Local, fast, zero-latency text-to-speech using ONNX models
# ============================================================
import asyncio
import io
import logging
import wave
from typing import Optional

from livekit import rtc
from livekit.agents import tts, utils
from livekit.agents.types import APIConnectOptions

logger = logging.getLogger("piper-tts")


class PiperTTS(tts.TTS):
    """LiveKit-compatible TTS using local Piper ONNX voice models."""

    def __init__(self, *, model_path: str):
        from piper import PiperVoice

        self._voice = PiperVoice.load(model_path)
        sample_rate = self._voice.config.sample_rate

        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=1,
        )
        logger.info(f"Piper TTS loaded: {model_path} (sample_rate={sample_rate})")

    def synthesize(
        self,
        text: str,
        *,
        conn_options: Optional[APIConnectOptions] = None,
    ) -> "PiperChunkedStream":
        return PiperChunkedStream(tts=self, input_text=text, voice=self._voice)


class PiperChunkedStream(tts.ChunkedStream):
    """Wraps Piper synthesis as a LiveKit ChunkedStream."""

    def __init__(
        self,
        *,
        tts: PiperTTS,
        input_text: str,
        voice,
    ):
        super().__init__(tts=tts, input_text=input_text)
        self._voice = voice

    async def _run(self) -> None:
        def _synthesize():
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                self._voice.synthesize(self._input_text, wf)
            buf.seek(0)
            with wave.open(buf, "rb") as wf:
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                pcm = wf.readframes(n_frames)
            return pcm, sample_rate, n_frames

        pcm, sample_rate, samples = await asyncio.get_event_loop().run_in_executor(
            None, _synthesize
        )

        frame = rtc.AudioFrame(
            data=pcm,
            sample_rate=sample_rate,
            num_channels=1,
            samples_per_channel=samples,
        )

        self._event_ch.send_nowait(
            tts.SynthesizedAudio(
                request_id=utils.shortuuid(),
                frame=frame,
                is_final=True,
            )
        )
