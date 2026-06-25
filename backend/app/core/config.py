from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = None # use .env URL
        
    class Config:
        env_file = [".env", "../.env"]
        env_file_encoding = "utf-8"
    
settings = Settings()