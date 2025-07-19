import os
from dotenv import load_dotenv

load_dotenv()

class Configuration:
    def __init__(self):
        self.supabase_url = os.getenv("R_SUPABASE_URL", "na")
        self.supabase_key = os.getenv("R_SUPABASE_KEY", "na")
        self.supabase_service_role_key = os.getenv("R_SUPABASE_SERVICE_ROLE_KEY", "na")
        self.secret_key = os.getenv("R_KEY", "default_secret")
        self.url = os.getenv("R_IP", "0.0.0.0")
        self.port = int(os.getenv("R_PORT", "8000"))
        self.email = os.getenv("R_EMAIL", "")

uconfig = Configuration()
