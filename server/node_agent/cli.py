import argparse
import asyncio
import sys
from .registration import register_with_control_plane
from .hardware.discovery import discover_all

def main():
    parser = argparse.ArgumentParser(description="AgentMesh Node Agent CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    register_parser = subparsers.add_parser("register")
    register_parser.add_argument("--control-plane-url", required=True)
    register_parser.add_argument("--owner-token", required=True)
    
    subparsers.add_parser("start")
    subparsers.add_parser("status")
    subparsers.add_parser("hardware")
    
    args = parser.parse_args()
    
    if args.command == "register":
        try:
            print("Discovering hardware...")
            hw = discover_all()
            print("Registering with control plane...")
            result = register_with_control_plane(args.control_plane_url, args.owner_token, hw)
            print(f"Registered successfully! Node ID: {result.get('node_id')}")
        except Exception as e:
            print(f"Registration failed: {e}")
            sys.exit(1)
            
    elif args.command == "start":
        from .main import app
        import uvicorn
        from .config import settings
        uvicorn.run(app, host=settings.NODE_AGENT_HOST, port=settings.NODE_AGENT_PORT)
        
    elif args.command == "status":
        from .registration import is_registered, load_registration
        if not is_registered():
            print("Node is not registered.")
        else:
            node_id, _ = load_registration()
            print(f"Node is registered. ID: {node_id}")
            
    elif args.command == "hardware":
        hw = discover_all()
        for k, v in hw.items():
            print(f"{k}: {v}")
            
if __name__ == "__main__":
    main()
