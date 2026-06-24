import os
import requests
import tempfile
import logging

logger = logging.getLogger(__name__)

ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
REFERRAL_AMOUNT   = 40
MIN_WITHDRAW      = 400
MIN_REFERRALS     = 10

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def build_caption(data: dict) -> str:
    parts = [data.get("caption", "")]
    if data.get("extra_words"):
        parts.append("")
        parts.extend(data["extra_words"])
    if data.get("watermark"):
        parts.append(f"\n{data['watermark']}")
    return "\n".join(parts)

def get_active_link(data: dict) -> dict | None:
    links = data.get("apk_links", [])
    idx   = data.get("active_link_index", 0)
    if links and 0 <= idx < len(links):
        return links[idx]
    return None

def human_size(num_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"

def download_file(url: str, suffix: str) -> tuple[str | None, int]:
    """Download file, return (temp_path, size_bytes). Returns (None, 0) on failure."""
    try:
        resp = requests.get(url, timeout=120, stream=True)
        resp.raise_for_status()
        size = 0
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in resp.iter_content(chunk_size=8192):
                tmp.write(chunk)
                size += len(chunk)
            return tmp.name, size
    except Exception as e:
        logger.error(f"Download failed ({url}): {e}")
        return None, 0

async def check_channel_membership(bot, user_id: int, channel_id) -> bool:
    """Returns True if user is a member of the required channel."""
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False
