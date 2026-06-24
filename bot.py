import os
import logging
from telegram import Update, Chat
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)

from utils.db import load_data, save_data, get_user, save_user
from utils.helpers import is_admin, ADMIN_IDS
from handlers.posting import scheduler, reschedule
from handlers.user import (
    cmd_start,
    show_user_menu,
    show_referral_menu,
    check_joined_callback,
    submit_screenshot_callback,
    request_withdraw_callback,
    handle_screenshot,
    handle_withdraw_number,
    handle_new_member,
    show_lang_select,
    handle_setlang,
)
from handlers.admin import (
    show_admin_menu,
    admin_callback,
    admin_message_handler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]

# ── Auto register/unregister when bot added/removed ───────────────────────────
async def handle_my_chat_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result:
        return
    chat       = result.chat
    new_status = result.new_chat_member.status

    if chat.type not in (Chat.GROUP, Chat.SUPERGROUP, Chat.CHANNEL):
        return

    data = load_data()

    if new_status in ("member", "administrator"):
        if not any(g["id"] == chat.id for g in data["groups"]):
            data["groups"].append({"id": chat.id, "title": chat.title or str(chat.id)})
            save_data(data)
            logger.info(f"Auto-registered: {chat.title}")

        try:
            await ctx.bot.send_message(
                chat.id,
                "👋 Hello! I've been added to this chat.\n\n"
                "📦 I will automatically post APK updates here on schedule.\n"
                "🔔 Stay tuned for the latest releases!"
            )
        except Exception as e:
            logger.warning(f"Welcome msg failed for {chat.title}: {e}")

        for admin_id in ADMIN_IDS:
            try:
                await ctx.bot.send_message(admin_id, f"✅ Added to *{chat.title}* — auto-registered!", parse_mode="Markdown")
            except Exception:
                pass

    elif new_status in ("left", "kicked"):
        before = len(data["groups"])
        data["groups"] = [g for g in data["groups"] if g["id"] != chat.id]
        if len(data["groups"]) < before:
            save_data(data)
            for admin_id in ADMIN_IDS:
                try:
                    await ctx.bot.send_message(admin_id, f"⚠️ Removed from *{chat.title}* — unregistered.", parse_mode="Markdown")
                except Exception:
                    pass

# ── Master callback router ─────────────────────────────────────────────────────
async def master_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    d = q.data

    # Admin callbacks
    if is_admin(q.from_user.id) and (
        d.startswith("a_") or
        d.startswith("approve_ref_") or
        d.startswith("reject_ref_") or
        d.startswith("pay_approve_") or
        d.startswith("pay_reject_")
    ):
        await admin_callback(update, ctx)
        return

    # Language selection
    if d.startswith("setlang_"):
        await handle_setlang(update, ctx)
        return

    # User callbacks
    if d == "check_joined":
        await check_joined_callback(update, ctx)
    elif d == "referral_menu":
        await show_referral_menu(update, ctx)
    elif d == "user_menu":
        await q.answer()
        await show_user_menu(update, ctx)
    elif d == "submit_screenshot":
        await submit_screenshot_callback(update, ctx)
    elif d == "request_withdraw":
        await request_withdraw_callback(update, ctx)
    elif d == "change_lang":
        await q.answer()
        await show_lang_select(update, ctx)
    elif d == "noop":
        await q.answer()

# ── Master message router ──────────────────────────────────────────────────────
async def master_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    user_id = update.effective_user.id

    # Admin message handling
    if is_admin(user_id):
        await admin_message_handler(update, ctx)
        return

    # User awaiting states
    data = load_data()
    user = get_user(data, user_id)

    if user.get("awaiting") == "screenshot" and update.message.photo:
        await handle_screenshot(update, ctx)
        return

    if user.get("awaiting") == "withdraw_number" and update.message.text:
        await handle_withdraw_number(update, ctx)
        return

# ── /help command ──────────────────────────────────────────────────────────────
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    if is_admin(update.effective_user.id):
        await show_admin_menu(update, ctx)
    else:
        await cmd_start(update, ctx)

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))

    # New member in group
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))

    # Bot added/removed from chat
    app.add_handler(ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    # All callbacks
    app.add_handler(CallbackQueryHandler(master_callback))

    # All private messages (text + photo + document)
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (filters.TEXT | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND,
        master_message,
    ))

    # Start scheduler
    scheduler.start()
    reschedule(app)

    logger.info("🤖 Bot started!")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
