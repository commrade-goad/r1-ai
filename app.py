import fastapi as f
from fastapi import HTTPException, status, Request
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from config import uconfig
from supabase import create_client, Client


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

        return response

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
                "data": {"name": payload.name}
                }
            })

        return response

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

@app.get("/profile")
async def get_profile(request: Request):
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth_header.split("Bearer ")[1]

    try:
        response = supabase.auth.get_user(jwt=token)
        return response
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

# TODO: Upload the pdf, Login admin, Register admin, Ask for the summerization
