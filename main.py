import gzip
import json
import os
import httpx
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Form
from init_data import InitData

app = FastAPI(title="Vidmage Custom Emoji API", version="1.0.0")

# Security and API Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")  # Must end in 'bot'


def verify_user(init_data: str) -> int:
    """Validates the HMAC-SHA256 signature sent by the Telegram Mini App.
    If no init_data is provided (e.g. testing from a browser/Swagger UI
    instead of inside Telegram), validation is skipped and a test user
    ID is returned instead."""
    if not init_data:
        return 123456789  # test/dev fallback user id

    if not InitData(init_data, BOT_TOKEN).validate():
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")

    # In production, parse init_data to extract the real user ID.
    return 123456789


def generate_tgs_from_svg(svg_content: bytes, main_color: str, accent_color: str) -> bytes:
    """Compiles the raw vector and colors into a gzipped Lottie JSON."""
    # Placeholder for actual Lottie JSON layer manipulation
    mock_lottie = {
        "v": "5.5.2",
        "fr": 60,
        "ip": 0,
        "op": 180,
        "w": 512,
        "h": 512,
        "nm": "vidmage_render",
        "layers": []
    }
    raw_json = json.dumps(mock_lottie, separators=(",", ":"))
    return gzip.compress(raw_json.encode("utf-8"))


async def upload_tgs(user_id: int, tgs_data: bytes) -> str:
    """Uploads the compiled animation to Telegram to retrieve a reusable file_id."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/uploadStickerFile"
    files = {"sticker": ("emoji.tgs", tgs_data, "application/gzip")}
    data = {"user_id": user_id, "sticker_format": "animated"}
    async with httpx.AsyncClient() as client:
        res = await client.post(url, data=data, files=files)
        res_data = res.json()
        if not res_data.get("ok"):
            raise HTTPException(status_code=400, detail=f"Upload failed: {res_data}")
        return res_data["result"]["file_id"]


async def publish_custom_emoji_set(user_id: int, file_id: str, base_name: str, title: str):
    """Binds the uploaded file into a new custom emoji sticker set."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/createNewStickerSet"
    full_pack_name = f"{base_name}_by_{BOT_USERNAME}"
    payload = {
        "user_id": user_id,
        "name": full_pack_name,
        "title": title,
        "sticker_type": "custom_emoji",
        "stickers": [
            {
                "sticker": file_id,
                "format": "animated",
                "emoji_list": ["✨"]
            }
        ]
    }
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json=payload)
        res_data = res.json()
        if not res_data.get("ok"):
            raise HTTPException(status_code=400, detail=f"Pack creation failed: {res_data}")
        return full_pack_name


@app.post("/create-telegram-pack")
async def create_pack(
    x_telegram_init_data: str = Header(None),
    logo_svg: UploadFile = File(...),
    main_color: str = Form("#0D1323"),
    accent_color: str = Form("#3B82F6"),
    pack_name: str = Form("vidmage_emojis")
):
    """Generates a custom animated emoji pack from an uploaded SVG logo."""
    user_id = verify_user(x_telegram_init_data)
    svg_bytes = await logo_svg.read()

    tgs_bytes = generate_tgs_from_svg(svg_bytes, main_color, accent_color)
    file_id = await upload_tgs(user_id, tgs_bytes)
    final_pack_name = await publish_custom_emoji_set(
        user_id=user_id,
        file_id=file_id,
        base_name=pack_name,
        title="Custom Animated Emojis"
    )

    return {
        "status": "success",
        "pack_url": f"https://t.me/addstickers/{final_pack_name}"
    }
