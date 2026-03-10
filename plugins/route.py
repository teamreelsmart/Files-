from aiohttp import web
import time

from config import VERIFY_MIN_TIME, FIRST_WARNING_TEXT, SECOND_WARNING_TEXT, WARNING_IMAGE_URL, LOG_CHANNEL_ID
from database.database import db_find_user_by_service_token
from helper_func import update_verify_status

routes = web.RouteTableDef()


def _page(title: str, subtitle: str, success: bool = False):
    color = '#22c55e' if success else '#3b82f6'
    return f"""
    <html>
      <head>
        <meta name='viewport' content='width=device-width, initial-scale=1'/>
        <title>{title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; background:#0f172a; color:#fff; display:flex; min-height:100vh; align-items:center; justify-content:center; }}
            .box {{ width:min(500px, 92vw); background:#111827; padding:24px; border-radius:16px; }}
            .bar {{ height:10px; border-radius:999px; background:#1f2937; overflow:hidden; margin-top:16px; }}
            .fill {{ height:100%; width:0%; background:{color}; animation:load 3s linear forwards; }}
            @keyframes load {{ from {{ width:0%; }} to {{ width:100%; }} }}
            .sub {{ color:#cbd5e1; margin-top:8px; }}
        </style>
      </head>
      <body>
        <div class='box'>
          <h2>{title}</h2>
          <p class='sub'>{subtitle}</p>
          <div class='bar'><div class='fill'></div></div>
        </div>
      </body>
    </html>
    """


async def _notify_user(bot, user_id: int, text: str):
    if WARNING_IMAGE_URL:
        await bot.send_photo(chat_id=user_id, photo=WARNING_IMAGE_URL, caption=text)
        return
    await bot.send_message(chat_id=user_id, text=text)


async def _log(bot, message: str):
    if LOG_CHANNEL_ID:
        await bot.send_message(chat_id=LOG_CHANNEL_ID, text=message)


@routes.get('/', allow_head=True)
async def root_route_handler(request):
    return web.json_response({"status": "ok", "service": "verification"})


@routes.get('/verify/{token}')
async def verify_route_handler(request):
    token = request.match_info['token']
    user = await db_find_user_by_service_token(token)
    if not user:
        return web.Response(text=_page("Invalid link", "Verification link is invalid or expired."), content_type='text/html')

    verify = user.get('verify_status', {})
    user_id = user['_id']
    bot = request.app['bot']

    if verify.get('is_banned'):
        return web.Response(text=_page("Access denied", "Your account is banned. Contact admin."), content_type='text/html')

    elapsed = time.time() - verify.get('token_created_at', 0)
    if elapsed < VERIFY_MIN_TIME:
        warnings = int(verify.get('warnings', 0)) + 1
        is_banned = warnings >= 2
        await update_verify_status(user_id, warnings=warnings, is_banned=is_banned)

        if is_banned:
            await _notify_user(bot, user_id, SECOND_WARNING_TEXT)
            await _log(bot, f"🚫 User banned\nUser: <a href='tg://user?id={user_id}'>{user_id}</a>\nReason: 2nd verification bypass warning")
        else:
            await _notify_user(bot, user_id, FIRST_WARNING_TEXT)
            await _log(bot, f"⚠️ First warning\nUser: <a href='tg://user?id={user_id}'>{user_id}</a>\nReason: verification attempted before wait time")

        return web.Response(text=_page("Verification blocked", "Suspicious activity detected. Please try again later."), content_type='text/html')

    target = verify.get('link')
    if not target:
        return web.Response(text=_page("Expired", "No active short link found. Generate a new token from bot."), content_type='text/html')

    html = _page("Verifying your access, please wait...", "Completing verification...") + f"""
    <script>
      setTimeout(async () => {{
        await fetch('/verify/{token}/complete', {{method: 'POST'}});
        document.querySelector('h2').innerText = 'Your verification completed successfully';
        document.querySelector('.sub').innerText = 'Redirecting, please wait...';
        setTimeout(() => window.location.href = '{target}', 1000);
      }}, 3000);
    </script>
    """
    return web.Response(text=html, content_type='text/html')


@routes.post('/verify/{token}/complete')
async def verify_complete_handler(request):
    token = request.match_info['token']
    user = await db_find_user_by_service_token(token)
    if not user:
        return web.json_response({"ok": False}, status=404)

    verify = user.get('verify_status', {})
    if verify.get('is_banned'):
        return web.json_response({"ok": False, "error": "banned"}, status=403)

    user_id = user['_id']
    await update_verify_status(
        user_id,
        is_verified=True,
        verified_time=time.time(),
        verify_token="",
        service_token="",
    )
    await _log(request.app['bot'], f"✅ Verification success\nUser: <a href='tg://user?id={user_id}'>{user_id}</a>")
    return web.json_response({"ok": True})


async def web_server(bot):
    web_app = web.Application(client_max_size=30000000)
    web_app['bot'] = bot
    web_app.add_routes(routes)
    return web_app
