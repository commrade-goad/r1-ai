import fastapi as f
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from config import uconfig
from supabase import create_client, Client
import base64
import datetime
import magic
import helper

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

class ChatWithAI(BaseModel):
    query: str
    hist_id: int | None = None


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
@app.post("/user/login")
async def login(payload: LoginRequest):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
            })

        return {"code": 200, "data": response}

    except Exception as e:
        return {"code": 400, "data": str(e)}

@app.post("/user/register")
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
@app.post("/user/edit")
async def edit_user(payload: EditUserRequest, user = Depends(get_current_user)):
    response = supabase.auth.admin.update_user_by_id(user.id, {"password": payload.password})
    if response.user:
        return {"code": 200, "data": "User password changed successfully."}
    return {"code": 500, "data": "Failed to change user password."}

@app.post("/user/info")
async def myself(user = Depends(get_current_user)):
    return {"code": 200, "data": user}


@app.post("/file/upload")
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


@app.post("/file/delete")
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


# get list of all the hist
@app.get("/history/get")
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

# delete hist
@app.get("/history/delete")
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

# create new hist manually
@app.get("/history/create")
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

# edit hist title
@app.get("/history/edit")
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

# get all of the chat from that hist id
@app.get("/chat/get-all")
async def aget_chat(hist_id: int, user = Depends(get_current_user)):
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

# send to ai and create the hist if didnt exist
@app.post("/chat/send")
async def post_chat(payload: ChatWithAI, user = Depends(get_current_user)):
    try:
        helper.chat_helper(supabase, user, payload.query, payload.hist_id)
    except Exception as e:
        return {"code": 500, "data": str(e)}

# send to ai and create the hist if didnt exist
@app.get("/chat/send")
async def get_chat(query: str, hist_id: int | None = None, user = Depends(get_current_user)):
    try:
        helper.chat_helper(supabase, user, query, hist_id)
    except Exception as e:
        return {"code": 500, "data": str(e)}


# TODO: Summerize, Edit Chat?, Edit File?
# NOTE: Seperate file
