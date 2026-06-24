import json
import os

DATA_FILE = "data.json"

DEFAULT_DATA = {
    # Bot settings
    "apk_links": [],
    "active_link_index": 0,
    "image_url": "",
    "video_url": "",
    "caption": "🚀 New update available!",
    "extra_words": [],
    "version": "1.0.0",
    "changelog": "Initial release",
    "watermark": "",

    # Groups & channels
    "groups": [],
    "required_channel_username": "@OfficialNovaDrop",
    "required_channel_id": 0,

    # Schedule
    "schedule_hour": 9,
    "schedule_minute": 0,
    "schedule_enabled": True,

    # Stats
    "total_posts": 0,
    "posts_per_group": {},

    # Users
    "users": {},
    # users[str(user_id)] = {
    #   "lang": "en",
    #   "balance": 0,
    #   "referrals": 0,
    #   "referred_by": null,
    #   "pending_withdraw": false,
    #   "withdraw_number": "",
    #   "awaiting": null,
    # }

    # Pending referral approvals
    "pending_referrals": [],
    # [{"from_user_id": int, "to_user_id": int, "msg_id": int}]

    # Pending withdrawals
    "pending_withdrawals": [],
    # [{"user_id": int, "amount": int, "number": str}]
}

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        for k, v in DEFAULT_DATA.items():
            data.setdefault(k, v)
        return data
    return DEFAULT_DATA.copy()

def save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user(data: dict, user_id: int) -> dict:
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "lang": "en",
            "balance": 0,
            "referrals": 0,
            "referred_by": None,
            "pending_withdraw": False,
            "withdraw_number": "",
            "awaiting": None,
        }
    return data["users"][uid]

def save_user(data: dict, user_id: int, user: dict):
    data["users"][str(user_id)] = user
    save_data(data)
