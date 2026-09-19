import asyncio
import json
import os
from datetime import datetime
import aiohttp
import discord
from discord.ext import tasks, commands
def load_token():
    t = os.environ.get("DISCORD_TOKEN", "").strip()
    if t:
        return t
    try:
        with open("token.txt", encoding="utf-8") as f:
            t = f.read().strip()
            if t:
                return t
    except Exception:
        pass
    return ""

TOKEN = load_token()
CHANNEL_ID = 1550756392778993756
SERVER_IP = "62.122.214.246"
SERVER_PORT = 25701
CONNECT_IP = "62.122.214.246:25701"
GAMEMONITORING_ID = 16660284
SERVER_NAME = "Z-HORROR | BETA | RU #1"
BANNER_URL = "https://cdn.discordapp.com/attachments/1485540687738048606/1550768632177365013/banner.png?ex=6aaf8955&is=6aae37d5&hm=a6b853a63fda55ec8efcf2685b254169674527182ce4b43c99ccf8bb2626a2cf&"
UPDATE_SECONDS = 60
SAVE_FILE = "stats_message.json"
try:
    from discord.ui import LayoutView, Container, TextDisplay, MediaGallery
    from discord.components import MediaGalleryItem
    HAS_V2 = True
except Exception:
    HAS_V2 = False
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def fetch_gamemonitoring():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
        async with s.get(f"https://api.gamemonitoring.ru/servers/{GAMEMONITORING_ID}") as r:
            server = (await r.json()).get("response", {})
        try:
            async with s.get(f"https://api.gamemonitoring.ru/servers/{GAMEMONITORING_ID}/players?limit=100") as r:
                players_data = (await r.json()).get("response", {}).get("items", [])
        except Exception:
            players_data = []
    players = []
    for p in players_data:
        name = p.get("name", "Unknown")
        secs = p.get("last_session_time") or 0
        if not secs:
            try:
                secs = int(p.get("last_online", 0)) - int(p.get("created", 0))
            except Exception:
                secs = 0
        if secs < 0:
            secs = 0
        players.append({"name": name, "duration": int(secs)})
    players.sort(key=lambda x: x["duration"], reverse=True)
    return {
        "name": server.get("name", SERVER_NAME or "GMod Server"),
        "map": server.get("map", "unknown"),
        "online": server.get("numplayers", len(players)),
        "max": server.get("maxplayers", 0),
        "status": server.get("status", False),
        "connect": server.get("connect", CONNECT_IP),
        "players": players,
    }

def fetch_a2s_sync():
    import a2s
    addr = (SERVER_IP, SERVER_PORT)
    info = a2s.info(addr, timeout=5.0)
    try:
        players_raw = a2s.players(addr, timeout=5.0)
    except Exception:
        players_raw = []
    players = [{"name": p.name or "Connecting...", "duration": int(p.duration)} for p in players_raw if p.name]
    players.sort(key=lambda x: x["duration"], reverse=True)
    return {
        "name": info.server_name,
        "map": info.map_name,
        "online": info.player_count,
        "max": info.max_players,
        "status": True,
        "connect": CONNECT_IP,
        "players": players,
    }

async def get_stats():
    try:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, fetch_a2s_sync)
        data["source"] = "a2s"
        return data
    except Exception as e:
        print(f"[A2S не ответил ({e}), беру GameMonitoring...]")
    data = await fetch_gamemonitoring()
    data["source"] = "gamemonitoring"
    return data

def short_name(name: str, limit: int = 20) -> str:
    name = name.strip()
    if len(name) > limit:
        return name[:limit - 1] + "..."
    return name

def format_mins(secs: int) -> str:
    if secs <= 0:
        return "в сети"
    mins = max(1, secs // 60)
    return f"{mins} мин."

def build_text(data: dict) -> str:
    display = SERVER_NAME or data["name"]
    if not data["status"]:
        return f"## Статистика: {display}\n```{CONNECT_IP}```\n:red_circle: **Сервер оффлайн**\nПробую переподключиться..."
    online = data["online"]
    mx = data["max"]
    mapa = data["map"]
    conn = data["connect"] or CONNECT_IP
    players = data["players"]
    lines = []
    lines.append(f"## Статистика: {display}")
    lines.append(f"{display} | `{conn}`")
    lines.append(f"Карта: `{mapa}`")
    lines.append(f"Онлайн: `{online}/{mx}`")
    lines.append(f"Подключение: `connect {conn}`")
    lines.append("─────────────────")
    lines.append("**Игроки:**")
    if not players:
        lines.append("*Сервер пуст*")
    else:
        for i, p in enumerate(players[:30], start=1):
            nick = short_name(p["name"])
            t = format_mins(p["duration"])
            lines.append(f"{i}. {nick} - `{t}`")
    lines.append(f"-# Обновлено • {datetime.now().strftime('%H:%M:%S')} • {conn}")
    return "\n".join(lines)

def build_view(data: dict):
    view = LayoutView(timeout=None)
    if BANNER_URL:
        box = Container(
            MediaGallery(MediaGalleryItem(media=BANNER_URL)),
            TextDisplay(content=build_text(data)),
            accent_colour=0x2B2D31,
        )
    else:
        box = Container(
            TextDisplay(content=build_text(data)),
            accent_colour=0x2B2D31,
        )
    view.add_item(box)
    return view

def build_embed(data: dict) -> discord.Embed:
    display = SERVER_NAME or data["name"]
    if not data["status"]:
        e = discord.Embed(
            title=f"Статистика: {display}",
            description=f"```{CONNECT_IP}```\n:red_circle: **Сервер оффлайн**\nПробую переподключиться...",
            color=0xED4245,
        )
        e.set_footer(text=f"Обновлено • {datetime.now().strftime('%H:%M:%S')}")
        return e
    online = data["online"]
    mx = data["max"]
    mapa = data["map"]
    conn = data["connect"] or CONNECT_IP
    players = data["players"]
    lines = []
    lines.append(f"{display} | `{conn}`")
    lines.append(f"Карта: `{mapa}`")
    lines.append(f"Онлайн: `{online}/{mx}`")
    lines.append(f"Подключение: `connect {conn}`")
    lines.append("─────────────────")
    lines.append("**Игроки:**")
    if not players:
        lines.append("*Сервер пуст*")
    else:
        for i, p in enumerate(players[:30], start=1):
            nick = short_name(p["name"])
            t = format_mins(p["duration"])
            lines.append(f"{i}. {nick} - `{t}`")
    e = discord.Embed(
        title=f"Статистика: {display}",
        description="\n".join(lines),
        color=0x2B2D31,
    )
    e.set_footer(text=f"Обновлено • {datetime.now().strftime('%H:%M:%S')} • {conn}")
    return e

async def send_stats(channel):
    data = await get_stats()
    if HAS_V2:
        return await channel.send(view=build_view(data)), data
    return await channel.send(embed=build_embed(data)), data

async def edit_stats(msg, data):
    if HAS_V2:
        await msg.edit(view=build_view(data))
    else:
        await msg.edit(embed=build_embed(data))

def load_saved():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_saved(channel_id: int, message_id: int):
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump({"channel_id": channel_id, "message_id": message_id}, f)

@tasks.loop(seconds=UPDATE_SECONDS)
async def updater():
    try:
        data = await get_stats()
    except Exception as e:
        print(f"[Ошибка получения статистики: {e}]")
        return
    try:
        if data["status"]:
            await bot.change_presence(activity=discord.Game(name=f"Онлайн {data['online']}/{data['max']}"))
        else:
            await bot.change_presence(activity=discord.Game(name="Сервер оффлайн"))
    except Exception:
        pass
    saved = load_saved()
    channel_id = CHANNEL_ID or saved.get("channel_id", 0)
    message_id = saved.get("message_id", 0)
    if not channel_id:
        print("[Настрой CHANNEL_ID в bot.py!]")
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            print(f"[Не могу найти канал {channel_id}: {e}]")
            return
    if message_id:
        try:
            msg = await channel.fetch_message(message_id)
            await edit_stats(msg, data)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Обновлено: {data['online']}/{data['max']} {data['map']}")
            return
        except Exception as e:
            print(f"[Старое сообщение не найдено, шлю новое: {e}]")
    try:
        msg, _ = await send_stats(channel)
        save_saved(channel.id, msg.id)
        print(f"[Отправлено новое сообщение статистики: {msg.id}]")
    except Exception as e:
        print(f"[Не могу отправить в канал: {e}]")

@updater.before_loop
async def before_updater():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user} | Канал: {CHANNEL_ID} | Сервер: {CONNECT_IP} | V2: {HAS_V2}")
    if not updater.is_running():
        updater.start()

@bot.command(name="stats")
async def cmd_stats(ctx):
    try:
        await send_stats(ctx.channel)
    except Exception as e:
        await ctx.send(f"Ошибка: {e}")

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def cmd_setup(ctx):
    msg, _ = await send_stats(ctx.channel)
    save_saved(ctx.channel.id, msg.id)
    await ctx.send(f"Готово! Это сообщение теперь будет обновляться каждые {UPDATE_SECONDS} сек. Не удаляй его.", delete_after=15)

if __name__ == "__main__":
    if not TOKEN:
        print("!!! Нет токена: положи токен в token.txt рядом с bot.py или задай переменную DISCORD_TOKEN !!!")
    else:
        bot.run(TOKEN)
