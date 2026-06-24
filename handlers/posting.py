import os
import logging
from telegram.ext import Application
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from utils.db import load_data, save_data
from utils.helpers import get_active_link, build_caption, download_file, human_size, ADMIN_IDS

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")

async def post_to_chat(app: Application, chat_id: int, chat_title: str = "") -> bool:
    data    = load_data()
    link    = get_active_link(data)
    if not link:
        logger.warning("No active APK link.")
        return False

    # Build caption with version info
    caption = build_caption(data)
    version   = data.get("version", "1.0.0")
    changelog = data.get("changelog", "")

    # 1️⃣ Image + caption
    image_url = data.get("image_url", "")
    if image_url:
        try:
            await app.bot.send_photo(chat_id=chat_id, photo=image_url, caption=caption)
        except Exception as e:
            logger.error(f"Image failed for {chat_title}: {e}")
            try:
                await app.bot.send_message(chat_id=chat_id, text=caption)
            except Exception:
                pass
    else:
        try:
            await app.bot.send_message(chat_id=chat_id, text=caption)
        except Exception as e:
            logger.error(f"Caption failed for {chat_title}: {e}")

    # 2️⃣ Installation video
    video_url = data.get("video_url", "")
    if video_url:
        path, _ = download_file(video_url, ".mp4")
        if path:
            try:
                with open(path, "rb") as vf:
                    await app.bot.send_video(chat_id=chat_id, video=vf, caption="📹 Installation Guide")
            except Exception as e:
                logger.error(f"Video failed for {chat_title}: {e}")
            finally:
                os.unlink(path)

    # 3️⃣ APK file
    path, size = download_file(link["url"], ".apk")
    if not path:
        return False
    try:
        apk_caption = f"📦 {link['label']} v{version}\n📝 {changelog}\n💾 {human_size(size)}"
        with open(path, "rb") as apk:
            await app.bot.send_document(
                chat_id=chat_id,
                document=apk,
                filename=f"{link['label']}_v{version}.apk",
                caption=apk_caption,
            )

        # Auto-pin if bot is admin
        try:
            sent = await app.bot.send_message(chat_id=chat_id, text="📌 Pinning latest update…")
            await app.bot.pin_chat_message(chat_id=chat_id, message_id=sent.message_id, disable_notification=True)
            await sent.delete()
        except Exception:
            pass  # Not admin or can't pin — skip silently

        logger.info(f"✅ Posted to {chat_title} ({chat_id})")
        return True
    except Exception as e:
        logger.error(f"APK failed for {chat_title}: {e}")
        return False
    finally:
        os.unlink(path)

async def post_to_all(app: Application):
    data   = load_data()
    groups = data.get("groups", [])
    if not groups:
        logger.warning("No groups configured.")
        return

    failed = []
    for group in groups:
        ok = await post_to_chat(app, group["id"], group["title"])
        if ok:
            data["total_posts"] = data.get("total_posts", 0) + 1
            ppg = data.setdefault("posts_per_group", {})
            ppg[group["title"]] = ppg.get(group["title"], 0) + 1
            save_data(data)
        else:
            failed.append(group["title"])

    if failed:
        for admin_id in ADMIN_IDS:
            try:
                await app.bot.send_message(admin_id, f"⚠️ Failed to post to: {', '.join(failed)}")
            except Exception:
                pass

def reschedule(app: Application):
    data = load_data()
    scheduler.remove_all_jobs()
    if data["schedule_enabled"]:
        scheduler.add_job(
            post_to_all,
            trigger="cron",
            hour=data["schedule_hour"],
            minute=data["schedule_minute"],
            args=[app],
            id="daily_post",
            replace_existing=True,
        )
        logger.info(f"Scheduled at {data['schedule_hour']}:{str(data['schedule_minute']).zfill(2)} UTC")
