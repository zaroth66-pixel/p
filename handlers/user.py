import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from utils.db import load_data, save_data, get_user, save_user
from utils.helpers import (
    is_admin, check_channel_membership, download_file,
    ADMIN_IDS, REFERRAL_AMOUNT, MIN_WITHDRAW, MIN_REFERRALS, human_size
)
from utils.languages import t, LANGUAGES

logger = logging.getLogger(__name__)

BOT_USERNAME = os.environ.get("BOT_USERNAME", "mybot")

# ── Language selection ─────────────────────────────────────────────────────────
async def show_lang_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = []
    row = []
    for code, name in LANGUAGES.items():
        row.append(InlineKeyboardButton(name, callback_data=f"setlang_{code}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    text = "🌍 Please select your language / እባክዎ ቋንቋዎን ይምረጡ / Afaan filadhaa / ቋንቋኻ ምረጽ"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def handle_setlang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    lang = q.data.split("_")[1]
    await q.answer()
    data = load_data()
    user = get_user(data, q.from_user.id)
    user["lang"] = lang
    save_user(data, q.from_user.id, user)
    await show_user_menu(update, ctx, lang)

# ── Send APK immediately ───────────────────────────────────────────────────────
async def send_apk_to_user(bot, user_id: int, lang: str):
    data = load_data()
    links = data.get("apk_links", [])
    idx   = data.get("active_link_index", 0)
    if not links:
        await bot.send_message(user_id, "⚠️ No APK available yet. Check back soon!")
        return

    link = links[idx]
    await bot.send_message(user_id, t(lang, "welcome"))

    # Send image
    if data.get("image_url"):
        try:
            await bot.send_photo(
                user_id,
                photo=data["image_url"],
                caption=f"📦 {link['label']} v{data.get('version','1.0')}"
            )
        except Exception as e:
            logger.warning(f"Image send failed: {e}")

    # Send video
    if data.get("video_url"):
        path, _ = download_file(data["video_url"], ".mp4")
        if path:
            try:
                with open(path, "rb") as vf:
                    await bot.send_video(user_id, video=vf, caption="📹 Installation Guide")
            except Exception as e:
                logger.warning(f"Video send failed: {e}")
            finally:
                os.unlink(path)

    # Send APK
    await bot.send_message(user_id, t(lang, "apk_caption"))
    path, size = download_file(link["url"], ".apk")
    if path:
        try:
            with open(path, "rb") as apk:
                await bot.send_document(
                    user_id,
                    document=apk,
                    filename=f"{link['label']}.apk",
                    caption=f"📦 {link['label']} v{data.get('version','1.0')} — {human_size(size)}",
                )
        except Exception as e:
            logger.error(f"APK send failed: {e}")
        finally:
            os.unlink(path)

# ── /start handler ─────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    args     = ctx.args

    # Admin goes to admin menu
    if is_admin(user_id):
        from handlers.admin import show_admin_menu
        await show_admin_menu(update, ctx)
        return

    data = load_data()
    user = get_user(data, user_id)

    # Handle referral param
    referred_by = None
    if args and args[0].startswith("ref_"):
        try:
            referred_by = int(args[0].split("_")[1])
            if referred_by == user_id:
                referred_by = None
        except Exception:
            referred_by = None

    if referred_by and not user.get("referred_by"):
        user["referred_by"] = referred_by

    save_user(data, user_id, user)

    lang = user.get("lang", "en")

    # First time or no lang set → ask language
    if not user.get("lang") or (args and args[0] == "setlang"):
        await show_lang_select(update, ctx)
        return

    # ✅ Send APK immediately — no gate
    await send_apk_to_user(ctx.bot, user_id, lang)

    # Then prompt channel join for features
    channel = data.get("required_channel_username", "@mychannel")
    joined  = await check_channel_membership(
        ctx.bot, user_id, data.get("required_channel_id") or channel
    )

    if not joined:
        kb = [
            [InlineKeyboardButton(t(lang, "join_btn"), url=f"https://t.me/{channel.lstrip('@')}")],
            [InlineKeyboardButton(t(lang, "check_join_btn"), callback_data="check_joined")],
        ]
        await update.message.reply_text(
            t(lang, "join_prompt"),
            reply_markup=InlineKeyboardMarkup(kb),
        )
    else:
        await show_user_menu(update, ctx, lang)

# ── User main menu ─────────────────────────────────────────────────────────────
async def show_user_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE, lang: str = None):
    user_id = update.effective_user.id
    data    = load_data()
    user    = get_user(data, user_id)
    lang    = lang or user.get("lang", "en")

    kb = [
        [InlineKeyboardButton(t(lang, "referral_menu"), callback_data="referral_menu")],
        [InlineKeyboardButton("🌍 " + t(lang, "lang_select"), callback_data="change_lang")],
    ]
    text = (
        f"{t(lang, 'main_menu')}\n\n"
        f"{t(lang, 'balance', balance=user.get('balance', 0))}\n"
        f"{t(lang, 'referrals_count', count=user.get('referrals', 0))}"
    )
    markup = InlineKeyboardMarkup(kb)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)

# ── Referral menu ──────────────────────────────────────────────────────────────
async def show_referral_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q       = update.callback_query
    user_id = q.from_user.id
    data    = load_data()
    user    = get_user(data, user_id)
    lang    = user.get("lang", "en")

    # Gate: must be in channel
    channel = data.get("required_channel_username", "@mychannel")
    joined  = await check_channel_membership(
        ctx.bot, user_id, data.get("required_channel_id") or channel
    )
    if not joined:
        kb = [
            [InlineKeyboardButton(t(lang, "join_btn"), url=f"https://t.me/{channel.lstrip('@')}")],
            [InlineKeyboardButton(t(lang, "check_join_btn"), callback_data="check_joined")],
        ]
        await q.edit_message_text(t(lang, "join_prompt"), reply_markup=InlineKeyboardMarkup(kb))
        return

    bot_username = (await ctx.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    balance  = user.get("balance", 0)
    refs     = user.get("referrals", 0)

    kb = [
        [InlineKeyboardButton(t(lang, "submit_screenshot"), callback_data="submit_screenshot")],
    ]
    if balance >= MIN_WITHDRAW and refs >= MIN_REFERRALS:
        kb.append([InlineKeyboardButton(t(lang, "withdraw_btn"), callback_data="request_withdraw")])
    kb.append([InlineKeyboardButton("⬅️ " + t(lang, "main_menu"), callback_data="user_menu")])

    text = (
        f"💰 *{t(lang, 'referral_menu')}*\n\n"
        f"{t(lang, 'balance', balance=balance)}\n"
        f"{t(lang, 'referrals_count', count=refs)}\n\n"
        f"{t(lang, 'referral_link', link=ref_link)}\n\n"
        f"{t(lang, 'share_text')}"
    )
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ── Check joined callback ──────────────────────────────────────────────────────
async def check_joined_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q       = update.callback_query
    user_id = q.from_user.id
    await q.answer()
    data    = load_data()
    user    = get_user(data, user_id)
    lang    = user.get("lang", "en")
    channel = data.get("required_channel_username", "@mychannel")
    joined  = await check_channel_membership(
        ctx.bot, user_id, data.get("required_channel_id") or channel
    )
    if joined:
        await q.edit_message_text(t(lang, "joined_confirm"))
        await show_user_menu(update, ctx, lang)
    else:
        await q.answer(t(lang, "not_joined"), show_alert=True)

# ── Screenshot submission ──────────────────────────────────────────────────────
async def submit_screenshot_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q       = update.callback_query
    user_id = q.from_user.id
    await q.answer()
    data    = load_data()
    user    = get_user(data, user_id)
    lang    = user.get("lang", "en")

    # Gate
    channel = data.get("required_channel_username", "@mychannel")
    joined  = await check_channel_membership(
        ctx.bot, user_id, data.get("required_channel_id") or channel
    )
    if not joined:
        await q.answer(t(lang, "not_joined"), show_alert=True)
        return

    user["awaiting"] = "screenshot"
    save_user(data, user_id, user)
    await q.edit_message_text(
        t(lang, "screenshot_prompt"),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="referral_menu")]]),
    )

async def handle_screenshot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """User sends a photo as screenshot proof."""
    user_id = update.effective_user.id
    if update.effective_chat.type != "private":
        return
    if is_admin(user_id):
        return

    data = load_data()
    user = get_user(data, user_id)
    lang = user.get("lang", "en")

    if user.get("awaiting") != "screenshot":
        return

    if not update.message.photo:
        await update.message.reply_text("❌ Please send a photo/screenshot.")
        return

    user["awaiting"] = None
    save_user(data, user_id, user)

    # Forward to each admin then immediately delete (no saving)
    referred_by = user.get("referred_by")
    caption = (
        f"📸 Screenshot from user {update.effective_user.full_name} "
        f"(ID: {user_id})\n"
        f"Referred by: {referred_by or 'None'}\n"
        f"Balance: {user.get('balance', 0)} ETB | Referrals: {user.get('referrals', 0)}"
    )

    sent_msg_ids = []
    for admin_id in ADMIN_IDS:
        try:
            fwd = await ctx.bot.forward_message(
                chat_id=admin_id,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id,
            )
            # Send approve/reject buttons to admin
            kb = [
                [
                    InlineKeyboardButton("✅ Approve (+40 ETB)", callback_data=f"approve_ref_{user_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_ref_{user_id}"),
                ]
            ]
            await ctx.bot.send_message(
                admin_id,
                caption,
                reply_markup=InlineKeyboardMarkup(kb),
            )
            sent_msg_ids.append((admin_id, fwd.message_id))
        except Exception as e:
            logger.error(f"Failed to forward screenshot to admin {admin_id}: {e}")

    # Delete original screenshot from bot memory (delete the user's message)
    try:
        await update.message.delete()
    except Exception:
        pass

    await ctx.bot.send_message(user_id, t(lang, "screenshot_sent"))

# ── Withdraw request ───────────────────────────────────────────────────────────
async def request_withdraw_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q       = update.callback_query
    user_id = q.from_user.id
    await q.answer()
    data    = load_data()
    user    = get_user(data, user_id)
    lang    = user.get("lang", "en")

    if user.get("balance", 0) < MIN_WITHDRAW or user.get("referrals", 0) < MIN_REFERRALS:
        await q.answer(t(lang, "withdraw_min"), show_alert=True)
        return

    if user.get("pending_withdraw"):
        await q.answer("⏳ You already have a pending withdrawal request.", show_alert=True)
        return

    user["awaiting"] = "withdraw_number"
    save_user(data, user_id, user)
    await q.edit_message_text(
        t(lang, "withdraw_prompt"),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="referral_menu")]]),
    )

async def handle_withdraw_number(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.effective_chat.type != "private" or is_admin(user_id):
        return
    data = load_data()
    user = get_user(data, user_id)
    lang = user.get("lang", "en")

    if user.get("awaiting") != "withdraw_number":
        return

    number = update.message.text.strip()
    user["awaiting"]        = None
    user["pending_withdraw"] = True
    user["withdraw_number"] = number
    save_user(data, user_id, user)

    # Notify admins
    name = update.effective_user.full_name
    for admin_id in ADMIN_IDS:
        try:
            kb = [
                [
                    InlineKeyboardButton("✅ Pay & Approve", callback_data=f"pay_approve_{user_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"pay_reject_{user_id}"),
                ]
            ]
            await ctx.bot.send_message(
                admin_id,
                f"💸 *Withdrawal Request*\n\n"
                f"👤 {name} (ID: {user_id})\n"
                f"💵 Amount: {user.get('balance', 0)} ETB\n"
                f"📱 Payment number: `{number}`",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")

    await update.message.reply_text(t(lang, "withdraw_sent"))

# ── New member joined group ────────────────────────────────────────────────────
async def handle_new_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """When a new member joins a group, tag them with a button."""
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        try:
            bot_username = (await ctx.bot.get_me()).username
            lang = "en"
            kb = [[InlineKeyboardButton(
                t(lang, "get_app_btn"),
                url=f"https://t.me/{bot_username}?start=welcome"
            )]]
            await update.message.reply_text(
                t(lang, "group_welcome", name=member.mention_html()),
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Welcome message failed: {e}")
