
import cloudinary
import cloudinary.uploader
import os
import json
import firebase_admin
from dotenv import load_dotenv


from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from firebase_admin import credentials, auth
from fastapi.middleware.cors import CORSMiddleware
from fastapi import (FastAPI, UploadFile, File, Form,
                     HTTPException, Depends, Header, Request)
# from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from linebot import LineBotApi
from linebot.models import TextSendMessage

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

firebase_creds = json.loads(os.getenv("FIREBASE_CREDENTIALS"))
cred = credentials.Certificate(firebase_creds)
firebase_admin.initialize_app(cred)


app = FastAPI()


origins = [
    "https://landdeedee-4sale.web.app",
    "https://www.landdeedee4sale.com",
    "https://landdeedee4sale.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# DDoss
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
# เพิ่ม TrustedHostMiddleware ถ้าจะจำกัดโดเมนที่เข้าถึงได้
# app.add_middleware(
#     TrustedHostMiddleware, allowed_hosts=[
#         "landdeedee-4sale.web.app",
#         "*.landdeedee-4sale.web.app"
#     ]
# )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."}
    )


async def verify_firebase_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(
            status_code=401, detail="Missing authorization header")

    token = authorization.replace("Bearer ", "")  # ดึง JWT Token ออกมา
    try:
        decoded_token = auth.verify_id_token(token)  # ตรวจสอบ JWT กับ Firebase
        return decoded_token  # คืนข้อมูลผู้ใช้ที่ยืนยันแล้ว
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@app.get("/healt")
@limiter.limit("3/minute")
async def root(
    request: Request,
):
    return {"message": "Hello world from Vee"}


@app.post("/upload/")
async def upload_image(
    file: UploadFile = File(...),
    folder_name: str = Form(...),
    user=Depends(verify_firebase_token)
):
    try:
        # Upload loudinary
        upload_result = cloudinary.uploader.upload(
            file.file, folder=folder_name, resource_type="image"
        )

        image_url = upload_result.get("secure_url")

        return {"image_url": image_url}

    except Exception as e:
        return {"error": str(e)}


@app.post("/bot-notify/")
@limiter.limit("3/minute")
async def send_line_message(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    content: str = Form(...),
):
    try:
        user_id = os.getenv("LINE_USER_ID")
        if not user_id:
            raise HTTPException(
                status_code=500, detail="LINE_USER_ID not configured")

        line_message = f""" 📩 ผู้สนใจใหม่จาก Landdeedee website

👤 ชื่อ-นามสกุล: {full_name}
📧 อีเมล: {email}
💬 ข้อความ: {message}
🏠 tag: {content}
                        """
        line_bot_api.push_message(user_id, TextSendMessage(text=line_message))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"LINE API error: {str(e)}")

# uvicorn main:app --host 0.0.0.0 --port 8000 --reload
