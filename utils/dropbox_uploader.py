import aiohttp
import asyncio
import base64
import json
from typing import Optional
from config import settings

class DropboxTokenManager:
    _access_token: Optional[str] = None
    _expires_at: float = 0.0
    _lock = asyncio.Lock()

    @classmethod
    async def get_access_token(cls) -> Optional[str]:
        if not settings.DROPBOX_ENABLED:
            return None
        if not (settings.DROPBOX_APP_KEY and settings.DROPBOX_APP_SECRET and settings.DROPBOX_REFRESH_TOKEN):
            return None

        import time
        async with cls._lock:
            # Refresh a bit before expiry
            if cls._access_token and time.time() < cls._expires_at - 30:
                return cls._access_token

            token_url = "https://api.dropboxapi.com/oauth2/token"
            data = {
                "grant_type": "refresh_token",
                "refresh_token": settings.DROPBOX_REFRESH_TOKEN,
            }

            auth_basic = base64.b64encode(f"{settings.DROPBOX_APP_KEY}:{settings.DROPBOX_APP_SECRET}".encode()).decode()

            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(token_url, data=data, headers={
                    "Authorization": f"Basic {auth_basic}",
                    "Content-Type": "application/x-www-form-urlencoded"
                }) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        print(f"Dropbox token refresh failed: {resp.status} {text[:200]}")
                        return None
                    payload = await resp.json()
                    cls._access_token = payload.get("access_token")
                    expires_in = payload.get("expires_in", 14400)  # default 4h
                    cls._expires_at = time.time() + float(expires_in)
                    return cls._access_token

class DropboxUploader:
    @staticmethod
    async def ensure_folder(access_token: str, path: str) -> bool:
        # Create folders recursively using create_folder_v2; ignore if exists
        api_url = "https://api.dropboxapi.com/2/files/create_folder_v2"
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {"path": path, "autorename": False}
            async with session.post(api_url, json=payload, headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }) as resp:
                if resp.status in (200, 409):
                    # 409 conflict means already exists
                    return True
                text = await resp.text()
                print(f"Dropbox ensure_folder failed for {path}: {resp.status} {text[:200]}")
                return False

    @staticmethod
    async def upload_file(local_path: str, dropbox_path: str) -> bool:
        """Upload a file to Dropbox at the specified path. Returns True on success.
        Creates missing folders under the base folder.
        """
        if not settings.DROPBOX_ENABLED:
            return False
        token = await DropboxTokenManager.get_access_token()
        if not token:
            return False

        # Ensure parent folder exists
        parent_folder = "/".join(dropbox_path.split("/")[:-1])
        if not parent_folder:
            parent_folder = "/"
        # Do not attempt to create root
        if parent_folder and parent_folder != "/":
            await DropboxUploader.ensure_folder(token, parent_folder)

        # Upload file
        content_url = "https://content.dropboxapi.com/2/files/upload"
        timeout = aiohttp.ClientTimeout(total=120)
        try:
            with open(local_path, "rb") as f:
                data = f.read()
        except Exception as e:
            print(f"Dropbox upload read error for {local_path}: {e}")
            return False

        args = {
            "path": dropbox_path,
            "mode": {".tag": "overwrite"},
            "autorename": False,
            "mute": True,
            "strict_conflict": False
        }

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(content_url, data=data, headers={
                "Authorization": f"Bearer {token}",
                "Dropbox-API-Arg": json.dumps(args),
                "Content-Type": "application/octet-stream"
            }) as resp:
                if resp.status == 200:
                    return True
                text = await resp.text()
                print(f"Dropbox upload failed for {dropbox_path}: {resp.status} {text[:200]}")
                return False

    @staticmethod
    def build_dropbox_path(*parts: str) -> str:
        base = settings.DROPBOX_BASE_FOLDER.strip("/") or "ExoMassChecker"
        path = "/" + "/".join([base] + [p.strip("/") for p in parts if p])
        return path
