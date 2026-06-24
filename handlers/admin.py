import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.db import load_data, save_data, get_user, save_user
from utils.helpers import is_admin, get_active_link, build_caption, ADMIN_IDS
from utils.languages import LANGUAGES

logger = logging.getLogger(__name__)

# ── Main admin menu ────────────────────────────────────────────────────────────
async def show_admin_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    link = get_active_link(data)
    h, m = data["schedule_hour"], str(data["schedule_minute"]).zfill(2)
    senbl = "✅ ON" if data["schedule_enabled"] else "❌ OFF"
    img   = "✅" if data.get("image_url") else "❌"
    vid   = "✅" if data.get("video_url") else "❌"

    kb = [
        [InlineKeyboardButton("📎 APK Links",            callback_data="a_links"),
         InlineKeyboardButton("🖼 Image",                callback_data="a_image")],
        [InlineKeyboardButton("📹 Video",                callback_data="a_video"),
         InlineKeyboardButton("💬 Caption & Words",      callback_data="a_caption")],
        [InlineKeyboardButton("🌍 Language Captions",    callback_data="a_langcaptions")],
        [InlineKeyboardButton("📦 Version & Changelog",  callback_data="a_version")],
        [InlineKeyboardButton("🔐 Channel Settings",     callback_data="a_channel")],
        [InlineKeyboardButton("👥 Groups",               callback_data="a_groups")],
        [InlineKeyboardButton("⏰ Schedule",             callback_data="a_schedule")],
        [InlineKeyboardButton("📤 Post Now",             callback_data="a_postnow"),
         InlineKeyboardButton("👁 Preview Post",         callback_data="a_preview")],
        [InlineKeyboardButton("📣 Broadcast",            callback_data="a_broadcast")],
        [InlineKeyboardButton("📊 Statistics",           callback_data="a_stats")],
        [InlineKeyboardButton("💾 Backup / Restore",     callback_data="a_backup")],
        [InlineKeyboardButton("🏷 Watermark",            callback_data="a_watermark")],
    ]
    text = (
        f"🤖 *Admin Panel*\n\n"
        f"📎 APK: {'✅ ' + link['label'] if link else '❌ None'}\n"
        f"🖼 Image: {img}  📹 Video: {vid}\n"
        f"👥 Groups: {len(data['groups'])}\n"
        f"📦 Version: v{data.get('version','1.0.0')}\n"
        f"⏰ Schedule: {h}:{m} UTC — {senbl}\n"
        f"👤 Users: {len(data.get('users',{}))}\n"
        f"📊 Total Posts: {data.get('total_posts',0)}"
    )
    markup = InlineKeyboardMarkup(kb)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")

# ── Callback router ────────────────────────────────────────────────────────────
async def admin_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    d = q.data
    await q.answer()

    if not is_admin(q.from_user.id):
        await q.answer("⛔ Not authorised.", show_alert=True)
        return

    # ── Back ──────────────────────────────────────────────────────────────────
    if d == "a_menu":
        await show_admin_menu(update, ctx)

    # ── APK Links ─────────────────────────────────────────────────────────────
    elif d == "a_links":         await show_links_menu(update, ctx)
    elif d == "a_addlink":
        ctx.user_data["a_awaiting"] = "link_label"
        await q.edit_message_text("📎 Send the *label* for this APK link:", parse_mode="Markdown")
    elif d.startswith("a_setactive_"):
        idx = int(d.split("_")[-1])
        data = load_data(); data["active_link_index"] = idx; save_data(data)
        await q.answer("✅ Active link set!", show_alert=True)
        await show_links_menu(update, ctx)
    elif d.startswith("a_dellink_"):
        idx = int(d.split("_")[-1])
        data = load_data()
        if 0 <= idx < len(data["apk_links"]):
            data["apk_links"].pop(idx)
            data["active_link_index"] = max(0, min(data["active_link_index"], len(data["apk_links"])-1))
            save_data(data)
        await show_links_menu(update, ctx)

    # ── Image ─────────────────────────────────────────────────────────────────
    elif d == "a_image":         await show_image_menu(update, ctx)
    elif d == "a_setimgurl":
        ctx.user_data["a_awaiting"] = "image_url"
        await q.edit_message_text("🖼 Send the direct image URL:")
    elif d == "a_uploadimg":
        ctx.user_data["a_awaiting"] = "image_upload"
        await q.edit_message_text("🖼 Send the image photo now:")
    elif d == "a_clearimg":
        data = load_data(); data["image_url"] = ""; save_data(data)
        await q.answer("🗑 Cleared.", show_alert=True); await show_image_menu(update, ctx)

    # ── Video ─────────────────────────────────────────────────────────────────
    elif d == "a_video":         await show_video_menu(update, ctx)
    elif d == "a_setvidurl":
        ctx.user_data["a_awaiting"] = "video_url"
        await q.edit_message_text("📹 Send the GitHub raw .mp4 URL:")
    elif d == "a_clearvid":
        data = load_data(); data["video_url"] = ""; save_data(data)
        await q.answer("🗑 Cleared.", show_alert=True); await show_video_menu(update, ctx)

    # ── Caption ───────────────────────────────────────────────────────────────
    elif d == "a_caption":       await show_caption_menu(update, ctx)
    elif d == "a_editcaption":
        ctx.user_data["a_awaiting"] = "caption"
        await q.edit_message_text("💬 Send the new main caption:")
    elif d == "a_addword":
        ctx.user_data["a_awaiting"] = "extra_word"
        await q.edit_message_text("➕ Send the extra line to add:")
    elif d.startswith("a_delword_"):
        idx = int(d.split("_")[-1])
        data = load_data()
        if 0 <= idx < len(data["extra_words"]):
            data["extra_words"].pop(idx); save_data(data)
        await show_caption_menu(update, ctx)

    # ── Language captions ─────────────────────────────────────────────────────
    elif d == "a_langcaptions":  await show_langcaptions_menu(update, ctx)
    elif d.startswith("a_editlangcap_"):
        lang = d.split("_")[-1]
        ctx.user_data["a_awaiting"]  = "lang_caption"
        ctx.user_data["a_lang_edit"] = lang
        await q.edit_message_text(f"💬 Send the caption for *{LANGUAGES.get(lang, lang)}*:", parse_mode="Markdown")

    # ── Version ───────────────────────────────────────────────────────────────
    elif d == "a_version":       await show_version_menu(update, ctx)
    elif d == "a_editversion":
        ctx.user_data["a_awaiting"] = "version"
        await q.edit_message_text("📦 Send new version number (e.g. `1.2.3`):", parse_mode="Markdown")
    elif d == "a_editchangelog":
        ctx.user_data["a_awaiting"] = "changelog"
        await q.edit_message_text("📝 Send the changelog for this version:")

    # ── Channel settings ──────────────────────────────────────────────────────
    elif d == "a_channel":       await show_channel_menu(update, ctx)
    elif d == "a_setchannel":
        ctx.user_data["a_awaiting"] = "channel_username"
        await q.edit_message_text("🔐 Send the channel username (e.g. `@mychannel`):", parse_mode="Markdown")
    elif d == "a_setchannelid":
        ctx.user_data["a_awaiting"] = "channel_id"
        await q.edit_message_text("🔢 Send the channel numeric ID (e.g. `-1001234567890`):")

    # ── Groups ────────────────────────────────────────────────────────────────
    elif d == "a_groups":        await show_groups_menu(update, ctx)
    elif d.startswith("a_delgroup_"):
        idx = int(d.split("_")[-1])
        data = load_data()
        if 0 <= idx < len(data["groups"]):
            removed = data["groups"].pop(idx); save_data(data)
            await q.answer(f"🗑 Removed: {removed['title']}", show_alert=True)
        await show_groups_menu(update, ctx)

    # ── Schedule ──────────────────────────────────────────────────────────────
    elif d == "a_schedule":      await show_schedule_menu(update, ctx)
    elif d == "a_togglesched":
        data = load_data(); data["schedule_enabled"] = not data["schedule_enabled"]; save_data(data)
        from handlers.posting import reschedule
        reschedule(ctx.application)
        await show_schedule_menu(update, ctx)
    elif d == "a_editsched":
        ctx.user_data["a_awaiting"] = "schedule_time"
        await q.edit_message_text("⏰ Send time in `HH:MM` UTC format (e.g. `08:30`):", parse_mode="Markdown")

    # ── Post now ──────────────────────────────────────────────────────────────
    elif d == "a_postnow":
        await q.edit_message_text("📤 Posting to all groups, please wait…")
        from handlers.posting import post_to_all
        await post_to_all(ctx.application)
        await q.edit_message_text(
            "✅ Done! Posted to all groups.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="a_menu")]]),
        )

    # ── Preview ───────────────────────────────────────────────────────────────
    elif d == "a_preview":
        await q.edit_message_text("👁 Sending preview to you now…")
        from handlers.posting import post_to_chat
        await post_to_chat(ctx.application, q.from_user.id, "Preview")
        await ctx.bot.send_message(
            q.from_user.id,
            "👁 That's how the post looks!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="a_menu")]]),
        )

    # ── Broadcast ─────────────────────────────────────────────────────────────
    elif d == "a_broadcast":
        ctx.user_data["a_awaiting"] = "broadcast"
        await q.edit_message_text(
            "📣 *Broadcast Message*\n\nSend the message to broadcast to ALL groups:",
            parse_mode="Markdown",
        )

    # ── Stats ─────────────────────────────────────────────────────────────────
    elif d == "a_stats":
        data  = load_data()
        total = data.get("total_posts", 0)
        users = len(data.get("users", {}))
        ppg   = data.get("posts_per_group", {})
        lines = [f"📊 *Statistics*\n", f"📤 Total posts: {total}", f"👤 Total users: {users}", ""]
        for gname, cnt in list(ppg.items())[:15]:
            lines.append(f"• {gname}: {cnt} posts")
        await q.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="a_menu")]]),
            parse_mode="Markdown",
        )

    # ── Backup ────────────────────────────────────────────────────────────────
    elif d == "a_backup":
        import json
        data = load_data()
        backup_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode()
        await ctx.bot.send_document(
            q.from_user.id,
            document=backup_bytes,
            filename="backup_data.json",
            caption="💾 Backup of bot data. Send this file back to restore.",
        )
        ctx.user_data["a_awaiting"] = "restore"
        await q.edit_message_text(
            "💾 Backup sent!\n\nTo restore, send the backup JSON file here.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="a_menu")]]),
        )

    # ── Watermark ─────────────────────────────────────────────────────────────
    elif d == "a_watermark":
        data = load_data()
        wm   = data.get("watermark", "") or "_Not set_"
        ctx.user_data["a_awaiting"] = "watermark"
        await q.edit_message_text(
            f"🏷 *Watermark*\n\nCurrent: {wm}\n\nSend new watermark text (or `clear` to remove):",
            parse_mode="Markdown",
        )

    # ── Referral approve/reject ───────────────────────────────────────────────
    elif d.startswith("approve_ref_"):
        uid  = int(d.split("_")[-1])
        data = load_data()
        user = get_user(data, uid)
        user["balance"]   = user.get("balance", 0) + 40
        user["referrals"] = user.get("referrals", 0) + 1
        save_user(data, uid, user)
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(f"✅ Approved! User {uid} got +40 ETB. Balance: {user['balance']} ETB")
        try:
            lang = user.get("lang", "en")
            await ctx.bot.send_message(uid, f"✅ Your referral screenshot was approved! +40 ETB added.\n💵 Balance: {user['balance']} ETB")
        except Exception: pass

    elif d.startswith("reject_ref_"):
        uid  = int(d.split("_")[-1])
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(f"❌ Rejected referral for user {uid}.")
        try:
            await ctx.bot.send_message(uid, "❌ Your screenshot was rejected. Please make sure you installed the app and try again.")
        except Exception: pass

    # ── Payout approve/reject ─────────────────────────────────────────────────
    elif d.startswith("pay_approve_"):
        uid  = int(d.split("_")[-1])
        data = load_data()
        user = get_user(data, uid)
        paid = user.get("balance", 0)
        user["balance"]         = 0
        user["pending_withdraw"] = False
        save_user(data, uid, user)
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(f"✅ Paid {paid} ETB to user {uid}. Balance reset to 0.")
        try:
            await ctx.bot.send_message(uid, f"✅ Your payout of {paid} ETB has been approved and sent!")
        except Exception: pass

    elif d.startswith("pay_reject_"):
        uid  = int(d.split("_")[-1])
        data = load_data()
        user = get_user(data, uid)
        user["pending_withdraw"] = False
        save_user(data, uid, user)
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(f"❌ Rejected payout for user {uid}.")
        try:
            await ctx.bot.send_message(uid, "❌ Your payout request was rejected. Contact admin for details.")
        except Exception: pass

# ── Sub-menus ─────────────────────────────────────────────────────────────────
async def show_links_menu(update, ctx):
    data  = load_data(); links = data["apk_links"]; ai = data["active_link_index"]
    kb = []
    for i, lnk in enumerate(links):
        star = "⭐ " if i == ai else ""
        kb.append([
            InlineKeyboardButton(f"{star}{lnk['label']}", callback_data=f"a_setactive_{i}"),
            InlineKeyboardButton("🗑", callback_data=f"a_dellink_{i}"),
        ])
    kb += [[InlineKeyboardButton("➕ Add Link", callback_data="a_addlink")],
           [InlineKeyboardButton("⬅️ Back",    callback_data="a_menu")]]
    await update.callback_query.edit_message_text(
        "📎 *APK Links* — tap to set active (⭐)",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_image_menu(update, ctx):
    data = load_data(); img = data.get("image_url","") or "_Not set_"
    kb = [
        [InlineKeyboardButton("🔗 Set URL",    callback_data="a_setimgurl"),
         InlineKeyboardButton("📤 Upload",     callback_data="a_uploadimg")],
        [InlineKeyboardButton("🗑 Clear",      callback_data="a_clearimg")],
        [InlineKeyboardButton("⬅️ Back",       callback_data="a_menu")],
    ]
    await update.callback_query.edit_message_text(
        f"🖼 *Image*\n\nCurrent: `{img[:80]}`",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_video_menu(update, ctx):
    data = load_data(); vid = data.get("video_url","") or "_Not set_"
    kb = [
        [InlineKeyboardButton("🔗 Set URL",    callback_data="a_setvidurl")],
        [InlineKeyboardButton("🗑 Clear",      callback_data="a_clearvid")],
        [InlineKeyboardButton("⬅️ Back",       callback_data="a_menu")],
    ]
    await update.callback_query.edit_message_text(
        f"📹 *Video*\n\nCurrent: `{vid[:80]}`",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_caption_menu(update, ctx):
    data = load_data()
    kb   = [[InlineKeyboardButton("✏️ Edit Caption", callback_data="a_editcaption")]]
    for i, w in enumerate(data.get("extra_words",[])):
        kb.append([InlineKeyboardButton(w[:35], callback_data="noop"),
                   InlineKeyboardButton("🗑", callback_data=f"a_delword_{i}")])
    kb += [[InlineKeyboardButton("➕ Add Line", callback_data="a_addword")],
           [InlineKeyboardButton("⬅️ Back",    callback_data="a_menu")]]
    await update.callback_query.edit_message_text(
        f"💬 *Caption*\n\n{data.get('caption','')}\n\nExtra lines: {len(data.get('extra_words',[]))}",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_langcaptions_menu(update, ctx):
    data = load_data()
    lang_captions = data.get("lang_captions", {})
    kb = []
    for code, name in LANGUAGES.items():
        has = "✅" if code in lang_captions else "➕"
        kb.append([InlineKeyboardButton(f"{has} {name}", callback_data=f"a_editlangcap_{code}")])
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data="a_menu")])
    await update.callback_query.edit_message_text(
        "🌍 *Language Captions*\n\nSet a custom caption per language. If not set, uses the default caption.",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_version_menu(update, ctx):
    data = load_data()
    kb = [
        [InlineKeyboardButton("📦 Edit Version",    callback_data="a_editversion")],
        [InlineKeyboardButton("📝 Edit Changelog",  callback_data="a_editchangelog")],
        [InlineKeyboardButton("⬅️ Back",            callback_data="a_menu")],
    ]
    await update.callback_query.edit_message_text(
        f"📦 *Version & Changelog*\n\nVersion: `v{data.get('version','1.0.0')}`\n\nChangelog:\n{data.get('changelog','—')}",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_channel_menu(update, ctx):
    data = load_data()
    ch   = data.get("required_channel_username","@mychannel")
    cid  = data.get("required_channel_id", 0)
    kb = [
        [InlineKeyboardButton("📝 Set Username",  callback_data="a_setchannel")],
        [InlineKeyboardButton("🔢 Set Channel ID",callback_data="a_setchannelid")],
        [InlineKeyboardButton("⬅️ Back",          callback_data="a_menu")],
    ]
    await update.callback_query.edit_message_text(
        f"🔐 *Channel Settings*\n\nUsername: `{ch}`\nID: `{cid}`\n\n_Both are needed for accurate membership verification._",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_groups_menu(update, ctx):
    data   = load_data(); groups = data["groups"]
    kb = []
    for i, g in enumerate(groups[:20]):
        kb.append([InlineKeyboardButton(g["title"][:30], callback_data="noop"),
                   InlineKeyboardButton("🗑", callback_data=f"a_delgroup_{i}")])
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data="a_menu")])
    await update.callback_query.edit_message_text(
        f"👥 *Groups & Channels*\n\nTotal: {len(groups)}\n\nBot auto-registers when added to any group/channel.",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_schedule_menu(update, ctx):
    data = load_data()
    h, m = data["schedule_hour"], str(data["schedule_minute"]).zfill(2)
    enbl = data["schedule_enabled"]
    kb = [
        [InlineKeyboardButton(f"{'✅ Enabled' if enbl else '❌ Disabled'} — Toggle", callback_data="a_togglesched")],
        [InlineKeyboardButton("⏰ Change Time", callback_data="a_editsched")],
        [InlineKeyboardButton("⬅️ Back",        callback_data="a_menu")],
    ]
    await update.callback_query.edit_message_text(
        f"⏰ *Schedule*\n\nTime: `{h}:{m} UTC`\nStatus: {'✅ ON' if enbl else '❌ OFF'}",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ── Admin text/file message handler ───────────────────────────────────────────
async def admin_message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    if not is_admin(user_id):
        return
    if update.effective_chat.type != "private":
        return

    awaiting = ctx.user_data.get("a_awaiting")
    if not awaiting:
        return

    # ── Photo upload ──────────────────────────────────────────────────────────
    if update.message.photo and awaiting == "image_upload":
        ctx.user_data.pop("a_awaiting", None)
        photo = update.message.photo[-1]
        file  = await photo.get_file()
        data  = load_data(); data["image_url"] = file.file_path; save_data(data)
        await update.message.reply_text("✅ Image uploaded!", reply_markup=_back_kb())
        return

    # ── Document restore ──────────────────────────────────────────────────────
    if update.message.document and awaiting == "restore":
        ctx.user_data.pop("a_awaiting", None)
        import json
        file     = await update.message.document.get_file()
        content  = await file.download_as_bytearray()
        try:
            restored = json.loads(content.decode())
            save_data(restored)
            await update.message.reply_text("✅ Data restored successfully!", reply_markup=_back_kb())
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to restore: {e}")
        return

    text = update.message.text.strip() if update.message.text else ""
    if not text:
        return

    data = load_data()
    ctx.user_data.pop("a_awaiting", None)

    if awaiting == "link_label":
        ctx.user_data["a_pending_label"] = text
        ctx.user_data["a_awaiting"]      = "link_url"
        await update.message.reply_text(f"✅ Label: *{text}*\n\nNow send the APK download URL:", parse_mode="Markdown")
        return

    elif awaiting == "link_url":
        label = ctx.user_data.pop("a_pending_label", "Unnamed")
        data["apk_links"].append({"label": label, "url": text})

    elif awaiting == "image_url":
        data["image_url"] = text

    elif awaiting == "video_url":
        data["video_url"] = text

    elif awaiting == "caption":
        data["caption"] = text

    elif awaiting == "extra_word":
        data.setdefault("extra_words", []).append(text)

    elif awaiting == "lang_caption":
        lang = ctx.user_data.pop("a_lang_edit", "en")
        data.setdefault("lang_captions", {})[lang] = text

    elif awaiting == "version":
        data["version"] = text.lstrip("v")

    elif awaiting == "changelog":
        data["changelog"] = text

    elif awaiting == "channel_username":
        data["required_channel_username"] = text if text.startswith("@") else f"@{text}"

    elif awaiting == "channel_id":
        try:
            data["required_channel_id"] = int(text)
        except ValueError:
            await update.message.reply_text("❌ Invalid ID. Must be a number like `-1001234567890`")
            return

    elif awaiting == "schedule_time":
        try:
            hh, mm = text.split(":")
            hh, mm = int(hh), int(mm)
            assert 0 <= hh <= 23 and 0 <= mm <= 59
            data["schedule_hour"]   = hh
            data["schedule_minute"] = mm
            save_data(data)
            from handlers.posting import reschedule
            reschedule(ctx.application)
            await update.message.reply_text(f"✅ Schedule set to `{hh}:{str(mm).zfill(2)} UTC`", parse_mode="Markdown", reply_markup=_back_kb())
            return
        except Exception:
            await update.message.reply_text("❌ Invalid format. Use HH:MM (e.g. 09:30)")
            return

    elif awaiting == "watermark":
        data["watermark"] = "" if text.lower() == "clear" else text

    elif awaiting == "broadcast":
        groups = data.get("groups", [])
        ok, fail = 0, 0
        for g in groups:
            try:
                await ctx.bot.send_message(g["id"], text)
                ok += 1
            except Exception:
                fail += 1
        await update.message.reply_text(f"📣 Broadcast done!\n✅ Sent: {ok}\n❌ Failed: {fail}", reply_markup=_back_kb())
        return

    save_data(data)
    await update.message.reply_text("✅ Saved!", reply_markup=_back_kb())

def _back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="a_menu")]])
