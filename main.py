import gzip
import json
import httpx
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Form
from init_data_python import InitData #

app = FastAPI(title="Vidmage Custom Emoji API", version="1.0.0")

# Security and API Configuration
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
BOT_USERNAME = "your_bot_username"  # Must end in 'bot'

def verify_user(init_data: str) -> int:
    """Validates the HMAC-SHA256 signature sent by the Telegram Mini App."""
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-Init-Data")
    
    # Validates the data string using the bot token to ensure it wasn't tampered with
    if not InitData(init_data, BOT_TOKEN).validate():
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")
    
    # In production, parse the init_data string to extract the actual user ID.
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
    
    # Telegram requires custom emoji sets to explicitly declare the sticker_type
    # The sticker pack name must strictly end with _by_<bot_username>
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
    """Main generation endpoint triggered by the frontend after payment."""
    user_id = verify_user(x_telegram_init_data)
    svg_bytes = await logo_svg.read()
    
    # 1. Process colors and SVG into an animated .tgs format
    tgs_bytes = generate_tgs_from_svg(svg_bytes, main_color, accent_color)
    
    # 2. Upload the .tgs to Telegram to secure a file_id
    file_id = await upload_tgs(user_id, tgs_bytes)
    
    # 3. Assemble and publish the custom emoji sticker set
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
