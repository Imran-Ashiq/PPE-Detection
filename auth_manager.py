import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

class AuthManager:
    def __init__(self):
        self.url: str = os.getenv("SUPABASE_URL")
        self.key: str = os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("Supabase credentials not found in .env file")
            
        self.supabase: Client = create_client(self.url, self.key)

    def login(self, email, password):
        try:
            response = self.supabase.auth.sign_in_with_password({
                "email": email, 
                "password": password
            })
            return {"success": True, "user": response.user, "session": response.session}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def signup(self, email, password):
        try:
            response = self.supabase.auth.sign_up({
                "email": email, 
                "password": password
            })
            # Check if auto-confirm is on or off. 
            # If off, user might be None or session might be None until confirmed.
            if response.user:
                return {"success": True, "user": response.user}
            else:
                return {"success": False, "error": "Signup failed. Please try again."}
        except Exception as e:
            return {"success": False, "error": str(e)}
