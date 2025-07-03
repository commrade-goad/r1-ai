import fastapi as f
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from config import uconfig
from supabase import create_client, Client
import base64
import datetime
import magic

#===================================================#
# Docs: https://supabase.com/docs/reference/python/ #
#===================================================#

#==============#
#  GLOBAL VAR  #
#==============#
app = f.FastAPI()
supabase: Client = create_client(
        uconfig.supabase_url,
        uconfig.supabase_key,
        )
security = HTTPBearer()

# -*- CALL THIS ON FIRST RUN -*- #
# import setup
# setup.create_admin_user(supabase, uconfig)


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

class DeleteChatRequest(BaseModel):
    chat_id: str

class DeleteUserRequest(BaseModel):
    user_uuid: str

class DeletePDFRequest(BaseModel):
    name: str

class EditUserRequest(BaseModel):
    password: str

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

# NOTE: For now only work on password
@app.post("/user-edit")
async def edit_user(request: Request, payload: EditUserRequest):
    token = check_auth(request)
    try:
        response = supabase.auth.get_user(jwt=token)
        if response is None:
            return {"success": False, "data": "Failed to get user info from that token."}

        response = supabase.auth.update_user({"password": payload.password})
        return {"success": True, "data": "User password changed successfully."}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/myself")
async def myself(request: Request):
    token = check_auth(request)
    try:
        response = supabase.auth.get_user(jwt=token)
        if response is None:
            return {"success": False, "data": "Failed to get user info from that token."}
        return response
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

# @app.post("/user-get")
# async def get_user(request: Request):
#     token = check_auth(request)
#     try:
#         response = supabase.auth.get_user(jwt=token)
#         if response is None:
#             return {"success": False, "data": "Failed to get user info from that token."}
#
#         is_admin = response.user.user_metadata.get("is_admin", False)
#         if is_admin is None:
#             return {"success": False, "data": "Only admin can get all user."}
#
#         response = supabase.auth.admin.list_users()
#         return {"success": True, "data": response}
#
#     except Exception as e:
#         raise HTTPException(status_code=401, detail=str(e))

# @app.post("/user-del")
# async def del_user(request: Request, payload: DeleteUserRequest):
#     token = check_auth(request)
#     try:
#         response = supabase.auth.get_user(jwt=token)
#         if response is None:
#             return {"success": False, "data": "Failed to get user info from that token."}
#
#         is_admin = response.user.user_metadata.get("is_admin", False)
#         if is_admin is False:
#             return {"success": False, "data": "Only admin can delete user."}
#
#         supabase.auth.admin.delete_user(payload.user_uuid)
#         return {"success": True, "data": "Successfully deleted the user"}
#
#     except Exception as e:
#         raise HTTPException(status_code=401, detail=str(e))

@app.post("/file-upload")
async def upload_file(payload: UploadPDFRequest, request: Request):
    token = check_auth(request)
    try:
        response = supabase.auth.get_user(jwt=token)
        if response is None:
            return {"success": False, "data": "Failed to get user info from that token."}

        is_admin = response.user.user_metadata.get("is_admin", False)
        if is_admin is False:
            return {"success": False, "data": "Only admin can upload pdf."}

        # NOTE: Not URL-Safe base64 if the safe variant use the down below.
        decoded_bytes = base64.b64decode(payload.data)
        # decoded_bytes = base64.urlsafe_b64decode(payload.data).decode('utf-8')

        if magic.from_buffer(decoded_bytes, mime=True) != "application/pdf":
            return {"success": False, "data": "The uploaded file is not a pdf."}

        file_path = f"public/{payload.name}" # assume there is .pdf already.
        file_call = (
            supabase.storage
            .from_("storage")
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

        if response.count is None:
            return {"success": False, "data": "Failed to insert the new file to the db."}

        return {"success": True, "data": file_call.full_path}

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/file-del")
async def del_file(request: Request, payload: DeletePDFRequest):
    token = check_auth(request)
    try:
        response = supabase.auth.get_user(jwt=token)
        if response is None:
            return {"success": False, "data": "Failed to get user info from that token."}

        is_admin = response.user.user_metadata.get("is_admin", False)
        if is_admin is False:
            return {"success": False, "data": "Only admin can delete user."}

        file_path = f"public/{payload.name}" # assume there is .pdf already.
        file_call = (
            supabase.storage
            .from_("storage")
            .remove([file_path])
        )

        if len(file_call) <= 0:
            return {"success": False, "data": f"Failed to delete file {payload.name}."}

        return {"success": True, "data": f"File {payload.name} deleted."}

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/file-get")
async def get_file(request: Request):
    token = check_auth(request)
    try:
        response = supabase.auth.get_user(jwt=token)
        if response is None:
            return {"success": False, "data": "Invalid JWT Token."}

        response = (
            supabase.table("file")
            .select("*")
            .execute()
        )
        if response.count is None:
            return {"success": False, "data": "Failed to get the file list."}
        return {"success": True, "data": response}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/chat-get")
async def get_chat(request: Request):
    token = check_auth(request)
    try:
        response = supabase.auth.get_user(jwt=token)
        if response is None:
            return {"success": False, "data": "Invalid JWT Token."}

        user_id = response.user.id
        response = (
            supabase.table("history")
            .select("*, file_used(*)")
            .eq("user_id", user_id)
            .execute()
        )
        if response.count is None:
            return {"success": False, "data": "Failed to get the chat."}
        return {"success": True, "data": response}

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/chat-del")
async def del_chat(request: Request, payload: DeleteChatRequest):
    token = check_auth(request)
    try:
        response = supabase.auth.get_user(jwt=token)
        if response is None:
            return {"success": False, "data": "Invalid JWT Token."}

        user_id = response.user.id
        response = (
                supabase.table("history")
                .delete()
                .eq("user_id", user_id)
                .eq("id", payload.chat_id)
                .execute()
        )
        if response.count is None:
            return {"success": False, "data": f"Failed to delete the chat with the id {payload.chat_id}."}
        return {"success": True, "data": f"Chat with the id {payload.chat_id} is deleted."}

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

# TODO: Finish this.
@app.post("/summerize")
async def summerize(q: str):
    return "WIP"

# TODO: Summerize, Edit Chat?, Edit File?
# NOTE: Pindah jadi table user?
# NOTE: pindah struktur return
# NOTE: Pakai Middleware untuk check token
# NOTE: Seperate file
