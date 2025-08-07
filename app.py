import fastapi as f
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Request, Depends, UploadFile, File, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from config import uconfig
from supabase import create_client, Client
from typing import List
import base64
import datetime
import magic
from rag_sermon_summarizer import summarize_sermon 
from typing import Optional
from rag_store_documents import process_and_add_documents

#===================================================#
# Docs: https://supabase.com/docs/reference/python/ #
#===================================================#

#==============#
#  GLOBAL VAR  #
#==============#
app = f.FastAPI()
# Tambahkan CORS middleware
origins = [
    "https://hegai.joelmedia.my.id",
    "http://localhost:5173", # For local development
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase: Client = create_client(
        uconfig.supabase_url,
        uconfig.supabase_key,
        )

# Admin client with service role key for admin operations
supabase_admin: Client = create_client(
        uconfig.supabase_url,
        uconfig.supabase_service_role_key if uconfig.supabase_service_role_key != "na" else uconfig.supabase_key,
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

class EditUserToAdminRequest(BaseModel):
    uid: str
    is_admin: bool

class DeleteFileRequest(BaseModel):
    file_name: str

class ChatRequest(BaseModel):
    user_id: str
    history_id: Optional[str] = None
    message: str
    file_path: Optional[str] = None  # Optional, can be None if no file is attached



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

# jadi admin    
# @app.put("/edit-user-to-admin", response_model=bool)
# def edit_user_to_admin(req: EditUserToAdminRequest, current_user = Depends(get_current_user)):
#     # Check if the current user is an admin
#     is_admin = current_user.user_metadata.get("is_admin", True)
#     if not is_admin:
#         raise HTTPException(status_code=403, detail="Only admin users can modify admin status")
    
#     try:
#         # Get the target user using admin client
#         user = supabase_admin.auth.admin.get_user_by_id(req.uid)
#         if user.user is None:
#             raise HTTPException(status_code=404, detail="User not found")

#         # Update user metadata using admin client
#         response = supabase_admin.auth.admin.update_user_by_id(
#             req.uid,
#             {"user_metadata": {"is_admin": req.is_admin}}
#         )
#         if response.user is None:
#             raise HTTPException(status_code=500, detail="Failed to update user")

#         return True
        
#     except Exception as e:
#         # Handle Supabase API errors
#         if "User not allowed" in str(e) or "403" in str(e):
#             raise HTTPException(status_code=403, detail="Insufficient permissions to perform admin operations")
#         raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}")


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
    response = supabase_admin.auth.admin.update_user_by_id(user.id, {"password": payload.password})
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


@app.post("/chat")
async def create_chat(request: ChatRequest):
    """
    Mengirim pesan baru
    """
    if not request.history_id:
        try:
            response = (supabase.table("history").insert(
                {
                    "user_id": request.user_id,
                    "title": request.message,
                }
            ).execute())

            rag_response = summarize_sermon(request.message)

            message_to_insert = [
                {
                    "history_id": response.data[0]["id"],
                    "role": "user",
                    "content": request.message,
                },
                {
                    "history_id": response.data[0]["id"],
                    "role": "assistant",
                    "content": rag_response.summary,
                }
            ]

            response = supabase.table("chat").insert(message_to_insert).execute()

            source_documents_to_insert = rag_response.source_documents if rag_response.source_documents else []

            for doc in source_documents_to_insert:
                supabase.table("chat_reference").insert({
                    "chat_id": response.data[1]["id"],
                    "reference": doc
                }).execute()

            response.data[1]["source_documents"] = rag_response.source_documents

            return {
                "code": 200,
                "data": response.data
            }
        except Exception as e:
            return {"code": 500, "data": str(e)}
    else:
        try:
            history_check = supabase.table("history").select("id").eq("id", request.history_id).execute()

            if history_check.count == 0:
                return {"code": 404, "data": "History not found or access denied"}

            rag_response = summarize_sermon(request.message)

            new_messages = [
                {
                    "history_id": request.history_id,
                    "role": "user",
                    "content": request.message,
                },
                {
                    "history_id": request.history_id,
                    "role": "assistant",
                    "content": rag_response.summary,
                }
            ]

            response = supabase.table("chat").insert(new_messages).execute()

            source_documents_to_insert = rag_response.source_documents if rag_response.source_documents else []

            for doc in source_documents_to_insert:
                supabase.table("chat_reference").insert({
                    "chat_id": response.data[1]["id"],
                    "reference": doc
                }).execute()

            response.data[1]["source_documents"] = rag_response.source_documents

            return {
                "code": 200,
                "data": response.data
            }
        except Exception as e:
            return {"code": 500, "data": str(e)}

@app.post("/update-knowledge", tags=["Knowledge Base"])
async def update_knowledge_base(
    files: List[UploadFile] = File(
        ...,
        description="Upload 1 hingga 5 file PDF untuk ditambahkan ke knowledge base.",
        max_items=5
    )
):
    """
    Endpoint ini menangani alur lengkap:
    1. Menerima file PDF (maksimal 5).
    2. Mengunggahnya ke Supabase Storage.
    3. Mengekstrak teks, membuat chunk, dan menghasilkan embedding.
    4. Menyimpan vektor embedding ke Pinecone.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tidak ada file yang diunggah."
        )

    # Validasi tipe file (hanya izinkan PDF)
    for file in files:
        if file.content_type != 'application/pdf':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{file.filename}' bukan PDF. Hanya file PDF yang diizinkan."
            )

    print(f"Menerima {len(files)} file untuk diproses...")
    
    # Panggil fungsi inti untuk melakukan semua pekerjaan berat
    result = await process_and_add_documents(files, supabase_admin)
    

    # Kembalikan respons berdasarkan hasil dari prosesor
    if result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["message"]
        )
    
    return result

// TODO: Delete on pinecone level.
@app.get("/file-delete")
async def delete_file(payload: DeleteFileRequest, user = Depends(get_current_user)):
    is_admin = user.user_metadata.get("is_admin", False)
    if is_admin is False:
        return {"code": 401, "data": "Only admin can delete pdf."}

    file_path = f"public/{payload.file_name}"
    file_call = (
        supabase.storage
        .from_("storage")
        .remove([file_path])
    )
    if len(file_call) <= 0
        return {"code": 500, "data": "Failed to delete the data."}

    try:
        _ = (
            supabase.table("file")
            .delete()
            .eq("file_name" payload.file_name)
            .execute()
        )
    except Exception as e:
        return {"code": 500, "data": str(e)}

    return {"code": 200, "data": "Data Deleted"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}


# TODO: Summerize, Edit Chat?, Edit File?
# NOTE: Seperate file
