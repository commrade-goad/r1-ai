import os
from dotenv import load_dotenv

load_dotenv()

class Configuration:
    def __init__(self):
        self.supabase_url = os.getenv("K_SUPABASE_URL", "na")
        self.supabase_key = os.getenv("K_SUPABASE_KEY", "na")
        self.secret_key = os.getenv("K_KEY", "default_secret")
        self.url = os.getenv("K_IP", "0.0.0.0")
        self.port = int(os.getenv("K_PORT", "8000"))

uconfig = Configuration()
