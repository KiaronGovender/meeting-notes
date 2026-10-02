import httpx

from ..config import settings

# Meeting BaaS API v2 (docs.meetingbaas.com/api-v2)
BASE = "https://api.meetingbaas.com/v2"


def _headers() -> dict:
    return {"x-meeting-baas-api-key": settings.meetingbaas_api_key, "Content-Type": "application/json"}


def send_bot(meeting_url: str, meeting_id: int, bot_name: str = "Notetaker") -> str:
    """Send a bot now. We transcribe ourselves with AssemblyAI, so Meeting BaaS transcription is off."""
    r = httpx.post(
        f"{BASE}/bots",
        headers=_headers(),
        json={
            "meeting_url": meeting_url,
            "bot_name": bot_name,
            "recording_mode": "speaker_view",  # or "audio_only" for smaller files
            "transcription_enabled": False,
            "callback_enabled": True,
            "callback_config": {
                "url": f"{settings.public_api_url}/webhooks/meetingbaas",
                "method": "POST",
                "secret": settings.webhook_secret,  # arrives as the x-mb-secret header
            },
            "extra": {"meeting_id": meeting_id},
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["data"]["bot_id"]


def get_bot(bot_id: str) -> dict:
    """Full details incl. fresh presigned video/audio URLs (valid ~4h)."""
    r = httpx.get(f"{BASE}/bots/{bot_id}", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()["data"]


def get_status(bot_id: str) -> str:
    r = httpx.get(f"{BASE}/bots/{bot_id}/status", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()["data"]["status"]


# Meeting BaaS status code -> our simpler status
def map_status(code: str) -> str:
    if code in ("completed",):
        return "done"
    if code in (
        "failed", "transcription_failed", "recording_failed", "bot_rejected", "bot_removed",
        "bot_removed_too_early", "waiting_room_timeout", "invalid_meeting_url", "meeting_error",
    ):
        return "failed"
    if code in ("in_call_recording", "recording_resumed", "recording_paused", "in_call_not_recording"):
        return "recording"
    if code in ("call_ended", "recording_succeeded", "transcribing"):
        return "processing"
    return "joining"  # queued, joining_call, in_waiting_room, ...
