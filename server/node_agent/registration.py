import os
import json
import httpx
from .config import settings
from .identity import get_or_create_identity, get_public_key_pem
from .hardware.discovery import discover_all

def get_config_path():
    return os.path.join(settings.DATA_DIR, "node_config.json")

def register_with_control_plane(control_plane_url, owner_api_key, hardware_info=None):
    if not hardware_info:
        hardware_info = discover_all()
        
    priv, pub = get_or_create_identity()
    pub_pem = get_public_key_pem(pub)
    
    import socket
    hostname = socket.gethostname()
    
    payload = {
        "name": hostname,
        "public_key": pub_pem,
        "hardware": hardware_info
    }
    
    headers = {
        "Authorization": f"Bearer {owner_api_key}"
    }
    
    response = httpx.post(
        f"{control_plane_url}/api/v1/nodes/register",
        json=payload,
        headers=headers,
        timeout=10.0
    )
    
    if response.status_code >= 400:
        raise Exception(f"Registration failed: {response.text}")
        
    data = response.json()
    node_id = data.get("node_id")
    api_key = data.get("api_key")
    
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    with open(get_config_path(), "w") as f:
        json.dump({"node_id": node_id, "api_key": api_key}, f)
        
    settings.NODE_ID = node_id
    settings.NODE_API_KEY = api_key
    
    return data

def is_registered():
    config_path = get_config_path()
    if not os.path.exists(config_path):
        return False
    try:
        with open(config_path, "r") as f:
            data = json.load(f)
            return bool(data.get("node_id") and data.get("api_key"))
    except (json.JSONDecodeError, OSError):
        return False

def load_registration():
    if not is_registered():
        return None, None
    with open(get_config_path(), "r") as f:
        data = json.load(f)
        settings.NODE_ID = data.get("node_id")
        settings.NODE_API_KEY = data.get("api_key")
        return settings.NODE_ID, settings.NODE_API_KEY
