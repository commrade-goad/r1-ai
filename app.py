import fastapi as f
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from config import uconfig
from supabase import create_client, Client
import base64
import datetime


#==============#
#  GLOBAL VAR  #
#==============#
app = f.FastAPI()
supabase: Client = create_client(
        uconfig.supabase_url,
        uconfig.supabase_key,
        )
security = HTTPBearer()


#==============#
#  MODELS      #
#==============#
class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class UploadPDFRequest(BaseModel):
    name: str
    data: str

#==============#
#  HELPER      #
#==============#
def check_auth(req: Request) -> str:
    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth_header.split("Bearer ")[1]
    return token

async def get_current_user(token: str = Depends(security)):
    try:
        user = supabase.auth.get_user(token)
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


#==============#
#  ROUTES      #
#==============#
@app.post("/login")
async def login(payload: LoginRequest):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
            })

        return {"success": True, "data": response}

    except Exception as e:
        raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
                )

@app.post("/register")
async def register(payload: RegisterRequest):
    try:
        response = supabase.auth.sign_up({
            "email": payload.email,
            "password": payload.password,
            "options": {
                "data": {
                    "name": payload.name,
                    "is_admin": False
                }
            }
        })

        return {"success": True, "data": response}

    except Exception as e:
        raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
                )

@app.post("/logout")
async def logout():
    try:
        supabase.auth.sign_out()
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
                )

@app.post("/upload-pdf")
async def upload_pdf(payload: UploadPDFRequest, request: Request):
    token = check_auth(request)
    try:
        response = supabase.auth.get_user(jwt=token)
        if response:
            is_admin = response.user.user_metadata.get("is_admin", False)
            if is_admin is False:
                return {"success": False, "data": "Only admin can upload pdf."}

        # NOTE: Not URL-Safe base64 if the safe variant use the down below.
        decoded_bytes = base64.b64decode(payload.data)
        # decoded_bytes = base64.urlsafe_b64decode(payload.data).decode('utf-8')

        file_path = f"public/{payload.name}" # assume there is .pdf already.
        response = (
            supabase.storage
            .from_("avatars")
            .upload(
                file=decoded_bytes,
                path=file_path,
                file_options={"cache-control": "3600", "upsert": "false"}
           )
        )
        response = (
            supabase.table("file")
            .insert(
                {"file_path": file_path, "file_name": payload.name, "uploaded_at": datetime.datetime.now(), "indexed": False}
            ).execute()
        )
        return {"success": True, "data": "WIP"}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/chat")
async def chat(request: Request):
    token = check_auth(request)
    try:
        pass
    except Exception as e:
        pass

@app.get("/summerize")
async def summerize(q: str):
    return "WIP"

# TODO: Ask for the summerization
