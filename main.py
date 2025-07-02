import uvicorn
from config import uconfig

if __name__ == "__main__":
    uvicorn.run("app:app", host=uconfig.url, port=uconfig.port, reload=True)
