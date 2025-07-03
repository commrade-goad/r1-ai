from supabase import Client
from config import Configuration

def create_admin_user(s: Client, uconfig: Configuration):
    response = s.auth.admin.create_user(
        {
            "email": uconfig.email,
            "password": uconfig.secret_key,
            "email_confirm": False,
            "user_metadata": {
                "name": "admin",
                "is_admin": True
            }
        }
    )

    if response.user:
        print("SUCCESS")
        return True

    print("FAILED")
    return False
