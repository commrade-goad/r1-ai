import fastapi as f
from fastapi import HTTPException, Request, Depends
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

class EditUserRequest(BaseModel):
    password: str

class DeleteUserRequest(BaseModel):
    user_uuid: str

class UploadPDFRequest(BaseModel):
    name: str
    data: str

class DeletePDFRequest(BaseModel):
    name: str

class DeleteHistRequest(BaseModel):
    hist_id: int

class CreateHistRequest(BaseModel):
    user_id: str
    title: str

class EditHistRequest(BaseModel):
    hist_id: int
    title: str


#==============#
#  HELPER      #
#==============#
def check_auth(req: Request) -> str:
    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth_header.split("Bearer ")[1]
    return token

async def get_current_user(request: Request):
    """Dependency to get current authenticated user"""
    token = check_auth(request)
    try:
        response = supabase.auth.get_user(jwt=token)
        if response is None:
            raise HTTPException(status_code=400, detail="Invalid JWT Token.")
        return response.user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


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

        return {"code": 200, "data": response}

    except Exception as e:
        return {"code": 400, "data": str(e)}

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

        return {"code": 200, "data": response}

    except Exception as e:
        return {"code": 400, "data": str(e)}

# NOTE: For now only work on password
@app.post("/user-edit")
async def edit_user(payload: EditUserRequest, user = Depends(get_current_user)):
    response = supabase.auth.admin.update_user_by_id(user.id, {"password": payload.password})
    if response.user:
        return {"code": 200, "data": "User password changed successfully."}
    return {"code": 500, "data": "Failed to change user password."}

@app.post("/myself")
async def myself(user = Depends(get_current_user)):
    return {"code": 200, "data": user}

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
async def upload_file(payload: UploadPDFRequest, user = Depends(get_current_user)):
    is_admin = user.user_metadata.get("is_admin", False)
    if is_admin is False:
        return {"code": 401, "data": "Only admin can upload pdf."}

    # NOTE: Not URL-Safe base64 if the safe variant use the down below.
    decoded_bytes = base64.b64decode(payload.data)
    # decoded_bytes = base64.urlsafe_b64decode(payload.data).decode('utf-8')

    if magic.from_buffer(decoded_bytes, mime=True) != "application/pdf":
        return {"code": 400, "data": "The uploaded file is not a pdf."}

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
    try:
        _ = (
            supabase.table("file")
            .insert(
                {"file_path": file_path, "file_name": payload.name, "uploaded_at": datetime.datetime.now(), "indexed": False}
            ).execute()
        )
    except Exception as e:
        return {"code": 500, "data": str(e)}

    return {"code": 200, "data": file_call.full_path}


@app.post("/file-del")
async def del_file(payload: DeletePDFRequest, user = Depends(get_current_user)):
    is_admin = user.user_metadata.get("is_admin", False)
    if is_admin is False:
        return {"code": 401, "data": "Only admin can delete user."}

    file_path = f"public/{payload.name}" # assume there is .pdf already.
    file_call = (
        supabase.storage
        .from_("storage")
        .remove([file_path])
    )

    if len(file_call) <= 0:
        return {"code": 500, "data": f"Failed to delete file {payload.name}."}

    return {"code": 200, "data": f"File {payload.name} deleted."}

# @app.post("/file-get")
# async def get_file(request: Request):
#     token = check_auth(request)
#     try:
#         response = supabase.auth.get_user(jwt=token)
#         if response is None:
#             return {"success": False, "data": "Invalid JWT Token."}
#
#         response = (
#             supabase.table("file")
#             .select("*")
#             .execute()
#         )
#
#         if response.count is None:
#             return {"code": 500, "data": "Failed to get the file list."}
#
#         return {"code": 200, "data": response}
#     except Exception as e:
#         raise HTTPException(status_code=401, detail=str(e))

@app.get("/hist-get")
async def get_hist(user = Depends(get_current_user)):
    user_id = user.id
    try:
        response = (
            supabase.table("history")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        return {"code": 200, "data": response}
    except Exception as e:
        return {"code": 500, "data": str(e)}

@app.get("/hist-del")
async def del_hist(payload: DeleteHistRequest, user = Depends(get_current_user)):
    user_id = user.id
    try:
        _ = (
            supabase.table("history")
            .delete()
            .eq("user_id", user_id)
            .eq("id", payload.hist_id)
            .execute()
        )
        return {"code": 200, "data": "History deleted"}
    except Exception as e:
        return {"code": 500, "data": str(e)}

@app.get("/hist-create")
async def create_hist(payload: CreateHistRequest, user = Depends(get_current_user)):
    try:
        response = (
            supabase.table("history")
            .insert(
                {
                    "user_id": user.id,
                    "title": payload.title,
                    "created_at": datetime.datetime.now()
                }
            )
            .execute()
        )
        return {"code": 200, "data": response}
    except Exception as e:
        return {"code": 500, "data": str(e)}

@app.get("/hist-edit")
async def edit_hist(payload: EditHistRequest, user = Depends(get_current_user)):
    response = None
    try:
        response = (
            supabase.table("history")
            .update(
                {
                    "title": payload.title,
                }
            )
            .eq("user_id", user.id)
            .execute()
        )
        return {"code": 200, "data": response}
    except Exception as e:
        return {"code": 500, "data": str(e)}

@app.get("/chat-get")
async def get_chat(hist_id: int, user = Depends(get_current_user)):
    try:
        response = (
            supabase.table("history")
            .select("*, chat(*)")
            .eq("user_id", user.id)
            .eq("id", hist_id)
            .execute()
        )

        if not response.data:
            return {"code": 404, "data": "History not found or access denied"}

        history_data = response.data[0]
        chats = sorted(
            history_data["chat"] or [],
            key=lambda x: x["created_at"]
        )

        return {"code": 200, "data": chats}

    except Exception as e:
        return {"code": 500, "data": str(e)}


# TODO: Finish this.
@app.post("/summerize")
async def summerize(q: str):
    return "WIP"

# TODO: Summerize, Edit Chat?, Edit File?
# NOTE: Seperate file
