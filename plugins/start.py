#(©)Codeflix_Bots

import logging
import random
import string
import time
import asyncio

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated

from bot import Bot
from config import (
    ADMINS,
    FORCE_MSG,
    START_MSG,
    CUSTOM_CAPTION,
    IS_VERIFY,
    VERIFY_EXPIRE,
    SHORTLINK_API,
    SHORTLINK_URL,
    DISABLE_CHANNEL_BUTTON,
    PROTECT_CONTENT,
    TUT_VID,
    SERVICE_BASE_URL,
)
from helper_func import subscribed, decode, get_messages, get_shortlink, get_verify_status, update_verify_status, get_exp_time
from database.database import add_user, del_user, full_userbase, present_user


@Bot.on_message(filters.command('start') & filters.private & subscribed)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id

    if not await present_user(user_id):
        try:
            await add_user(user_id)
        except Exception:
            pass

    verify_status = await get_verify_status(user_id)

    if verify_status.get('is_banned'):
        return await message.reply("🚫 You are banned from using this bot. Please contact admin.")

    if verify_status['is_verified'] and VERIFY_EXPIRE < (time.time() - verify_status['verified_time']):
        await update_verify_status(user_id, is_verified=False)
        verify_status['is_verified'] = False

    if len(message.command) > 1 and message.command[1].startswith('verify_'):
        token = message.command[1].split('verify_', 1)[1]
        if verify_status.get('verify_token') != token:
            return await message.reply("Your token is invalid or expired. Generate a new token from /start")

        await update_verify_status(user_id, is_verified=True, verified_time=time.time(), verify_token="", service_token="")
        return await message.reply("✅ Your token is verified and active now.")

    if len(message.command) > 1 and verify_status['is_verified']:
        base64_string = message.command[1]
        _string = await decode(base64_string)
        argument = _string.split("-")
        if len(argument) == 3:
            try:
                start = int(int(argument[1]) / abs(client.db_channel.id))
                end = int(int(argument[2]) / abs(client.db_channel.id))
            except Exception:
                return
            if start <= end:
                ids = range(start, end + 1)
            else:
                ids = []
                i = start
                while True:
                    ids.append(i)
                    i -= 1
                    if i < end:
                        break
        elif len(argument) == 2:
            try:
                ids = [int(int(argument[1]) / abs(client.db_channel.id))]
            except Exception:
                return
        else:
            return

        temp_msg = await message.reply("Please wait...")
        try:
            messages = await get_messages(client, ids)
        except Exception:
            await message.reply_text("Something went wrong..!", quote=True)
            return
        await temp_msg.delete()

        snt_msgs = []
        for msg in messages:
            caption = CUSTOM_CAPTION.format(previouscaption="" if not msg.caption else msg.caption.html, filename=msg.document.file_name) if bool(CUSTOM_CAPTION) and bool(msg.document) else "" if not msg.caption else msg.caption.html
            reply_markup = msg.reply_markup if DISABLE_CHANNEL_BUTTON else None
            try:
                snt_msg = await msg.copy(chat_id=message.from_user.id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup, protect_content=PROTECT_CONTENT)
                await asyncio.sleep(0.5)
                snt_msgs.append(snt_msg)
            except FloodWait as e:
                await asyncio.sleep(e.x)
                snt_msg = await msg.copy(chat_id=message.from_user.id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup, protect_content=PROTECT_CONTENT)
                snt_msgs.append(snt_msg)
            except Exception:
                pass

        sd = await message.reply_text("Files will be deleted after 600 seconds. Save them to saved messages now.")
        await asyncio.sleep(600)

        for snt_msg in snt_msgs:
            try:
                await snt_msg.delete()
                await sd.delete()
            except Exception:
                pass
        return

    if verify_status['is_verified']:
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("About Me", callback_data="about"), InlineKeyboardButton("Close", callback_data="close")]]
        )
        return await message.reply_text(
            text=START_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else '@' + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id,
            ),
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            quote=True,
        )

    if IS_VERIFY and not verify_status['is_verified']:
        if not SERVICE_BASE_URL:
            return await message.reply("SERVICE_BASE_URL is not configured. Add your Render URL and restart bot.")

        ad_token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        service_token = ''.join(random.choices(string.ascii_letters + string.digits, k=20))

        ad_link = await get_shortlink(SHORTLINK_URL, SHORTLINK_API, f'https://telegram.dog/{client.username}?start=verify_{ad_token}')
        service_link = f"{SERVICE_BASE_URL.rstrip('/')}/verify/{service_token}"

        await update_verify_status(
            user_id,
            verify_token=ad_token,
            service_token=service_token,
            link=ad_link,
            service_link=service_link,
            token_created_at=time.time(),
            is_verified=False,
        )

        btn = [
            [InlineKeyboardButton("🔐 Verify Access", url=service_link)],
            [InlineKeyboardButton('How to use the bot', url=TUT_VID)],
        ]
        return await message.reply(
            f"Your token expired. Generate new access.\n\nToken timeout: {get_exp_time(VERIFY_EXPIRE)}\n\nOpen verify link and complete step.",
            reply_markup=InlineKeyboardMarkup(btn),
            protect_content=False,
            quote=True,
        )


WAIT_MSG = "<b>ᴡᴏʀᴋɪɴɢ....</b>"
REPLY_ERROR = "<code>Use this command as a reply to any telegram message without any spaces.</code>"


@Bot.on_message(filters.command('start') & filters.private)
async def not_joined(client: Client, message: Message):
    buttons = [
        [
            InlineKeyboardButton(text="• ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", url=client.invitelink2),
            InlineKeyboardButton(text="ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ •", url=client.invitelink3),
        ],
        [
            InlineKeyboardButton(text="• ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ •", url=client.invitelink),
        ],
    ]
    try:
        buttons.append([
            InlineKeyboardButton(text='• ɴᴏᴡ ᴄʟɪᴄᴋ ʜᴇʀᴇ •', url=f"https://t.me/{client.username}?start={message.command[1]}")
        ])
    except IndexError:
        pass

    await message.reply(
        text=FORCE_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=None if not message.from_user.username else '@' + message.from_user.username,
            mention=message.from_user.mention,
            id=message.from_user.id,
        ),
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True,
        disable_web_page_preview=True,
    )


@Bot.on_message(filters.command('users') & filters.private & filters.user(ADMINS))
async def get_users(client: Bot, message: Message):
    msg = await client.send_message(chat_id=message.chat.id, text=WAIT_MSG)
    users = await full_userbase()
    await msg.edit(f"{len(users)} users are using this bot")


@Bot.on_message(filters.private & filters.command('broadcast') & filters.user(ADMINS))
async def send_text(client: Bot, message: Message):
    if message.reply_to_message:
        query = await full_userbase()
        broadcast_msg = message.reply_to_message
        total = successful = blocked = deleted = unsuccessful = 0

        pls_wait = await message.reply("<i>Broadcast processing...</i>")
        for chat_id in query:
            try:
                await broadcast_msg.copy(chat_id)
                successful += 1
            except FloodWait as e:
                await asyncio.sleep(e.x)
                await broadcast_msg.copy(chat_id)
                successful += 1
            except UserIsBlocked:
                await del_user(chat_id)
                blocked += 1
            except InputUserDeactivated:
                await del_user(chat_id)
                deleted += 1
            except Exception as e:
                unsuccessful += 1
                logging.error(f"Broadcast Error: {e}")
            total += 1

        status = f"""<b><u>Broadcast Completed</u>

Total users: <code>{total}</code>
Successful: <code>{successful}</code>
Blocked users: <code>{blocked}</code>
Deleted accounts: <code>{deleted}</code>
Unsuccessful: <code>{unsuccessful}</code></b>"""
        return await pls_wait.edit(status)

    msg = await message.reply(REPLY_ERROR)
    await asyncio.sleep(8)
    await msg.delete()
