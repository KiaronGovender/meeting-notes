import time

import httpx

from ..config import settings

BASE = "https://api.assemblyai.com/v2"


class AssemblyAITranscriber:
    """Returns segments: [{speaker, start_ms, end_ms, text}] using speaker-labelled utterances."""

    def transcribe(self, media_url: str) -> list[dict]:
        h = {"authorization": settings.assemblyai_api_key}
        r = httpx.post(
            f"{BASE}/transcript",
            headers=h,
            json={"audio_url": media_url, "speaker_labels": True},
            timeout=60,
        )
        r.raise_for_status()
        tid = r.json()["id"]
        while True:
            p = httpx.get(f"{BASE}/transcript/{tid}", headers=h, timeout=60).json()
            if p["status"] == "completed":
                break
            if p["status"] == "error":
                raise RuntimeError(p.get("error", "AssemblyAI transcription failed"))
            time.sleep(3)
        return [
            {
                "speaker": f"Speaker {u['speaker']}",
                "start_ms": u["start"],
                "end_ms": u["end"],
                "text": u["text"],
            }
            for u in p.get("utterances") or []
        ]
