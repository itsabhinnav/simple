#!/usr/bin/env python3
"""
Standalone Mock Artifactory Server

This mock server serves database files directly from its own folder,
following the flow: Angular -> Flask -> Mock Server -> File -> Flask -> Angular
"""

import json
import os
from datetime import datetime
from pathlib import Path
import asyncio
from aiohttp import web, ClientSession
from aiohttp.web import Request, Response, json_response

class FileBasedMockStorage:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.users = {"admin": "password"}
        self._ensure_sample_db()
    
    def _ensure_sample_db(self):
        """Ensure the sample database exists in the data directory."""
        sample_db_path = self.data_dir / "enhanced_sample_db.db"
        if not sample_db_path.exists():
            # Copy from current directory if it exists
            current_db = Path("enhanced_sample_db.db")
            if current_db.exists():
                import shutil
                shutil.copy2(current_db, sample_db_path)
                print(f"✅ Copied sample database to {sample_db_path}")
            else:
                print(f"⚠️ Sample database not found. Please ensure enhanced_sample_db.db exists.")
    
    def authenticate(self, username: str, password: str) -> bool:
        return self.users.get(username) == password
    
    def get_file_info(self, filename: str) -> dict:
        """Get information about a file."""
        file_path = self.data_dir / filename
        if file_path.exists():
            stat = file_path.stat()
            return {
                "repo": "generic-local",
                "path": filename,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            }
        return None
    
    def list_files(self) -> list:
        """List all files in the data directory."""
        files = []
        for file_path in self.data_dir.glob("*.db"):
            info = self.get_file_info(file_path.name)
            if info:
                files.append(info)
        return files
    
    def get_file_content(self, filename: str) -> bytes:
        """Get the content of a file."""
        file_path = self.data_dir / filename
        if file_path.exists():
            return file_path.read_bytes()
        return b""
    
    def store_file(self, filename: str, content: bytes) -> dict:
        """Store file content."""
        file_path = self.data_dir / filename
        file_path.write_bytes(content)
        return self.get_file_info(filename)

# Global storage instance
storage = FileBasedMockStorage()

async def ping_handler(request: Request) -> Response:
    """Health check endpoint."""
    return json_response({
        "status": "ok",
        "message": "Mock Artifactory Server is running",
        "timestamp": datetime.now().isoformat(),
        "data_directory": str(storage.data_dir.absolute())
    })

async def auth_handler(request: Request) -> Response:
    """Authentication endpoint."""
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")
        
        if storage.authenticate(username, password):
            return json_response({
                "message": "Authentication successful",
                "username": username,
                "timestamp": datetime.now().isoformat()
            })
        else:
            return json_response({
                "error": "Invalid credentials"
            }, status=401)
    except Exception as e:
        return json_response({
            "error": f"Authentication failed: {str(e)}"
        }, status=400)

async def upload_handler(request: Request) -> Response:
    """File upload endpoint."""
    try:
        # Extract filename from URL
        path_info = request.match_info.get('path', '')
        filename = path_info.split('/')[-1] if path_info else "unknown.db"
        
        # Read the uploaded file
        reader = await request.multipart()
        field = await reader.next()
        
        if field.name == 'file':
            data = await field.read()
            
            result = storage.store_file(filename, data)
            return json_response(result, status=201)
        else:
            return json_response({
                "error": "No file provided"
            }, status=400)
            
    except Exception as e:
        return json_response({
            "error": f"Upload failed: {str(e)}"
        }, status=500)

async def download_handler(request: Request) -> Response:
    """File download endpoint."""
    try:
        path_info = request.match_info.get('path', '')
        filename = path_info.split('/')[-1] if path_info else ""
        
        data = storage.get_file_content(filename)
        
        if data:
            return web.Response(
                body=data,
                headers={
                    'Content-Type': 'application/octet-stream',
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
        else:
            return json_response({
                "error": "File not found"
            }, status=404)
            
    except Exception as e:
        return json_response({
            "error": f"Download failed: {str(e)}"
        }, status=500)

async def list_handler(request: Request) -> Response:
    """List files endpoint."""
    try:
        files = storage.list_files()
        
        return json_response({
            "artifacts": files,
            "count": len(files),
            "repo": "generic-local",
            "data_directory": str(storage.data_dir.absolute())
        })
        
    except Exception as e:
        return json_response({
            "error": f"List failed: {str(e)}"
        }, status=500)

def create_app():
    """Create the web application."""
    app = web.Application()
    
    # Add routes
    app.router.add_get('/api/system/ping', ping_handler)
    app.router.add_post('/api/security/token', auth_handler)
    app.router.add_post('/api/storage/generic-local/{path:.+}', upload_handler)
    app.router.add_get('/api/storage/generic-local/{path:.+}', download_handler)
    app.router.add_get('/api/storage/generic-local', list_handler)
    
    return app

async def main():
    """Main function."""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python mock_server.py <port>")
        sys.exit(1)
    
    port = int(sys.argv[1])
    
    app = create_app()
    
    print(f"🚀 Starting Standalone Mock Artifactory Server on port {port}")
    print(f"📁 Data directory: {storage.data_dir.absolute()}")
    print(f"📡 Endpoints:")
    print(f"   GET  /api/system/ping - Health check")
    print(f"   POST /api/security/token - Authentication")
    print(f"   POST /api/storage/generic-local/{{path}} - Upload file")
    print(f"   GET  /api/storage/generic-local/{{path}} - Download file")
    print(f"   GET  /api/storage/generic-local - List files")
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, 'localhost', port)
    await site.start()
    
    print(f"✅ Mock server running on http://localhost:{port}")
    print(f"📊 Available files:")
    files = storage.list_files()
    for file_info in files:
        print(f"   - {file_info['path']} ({file_info['size']:,} bytes)")
    print("Press Ctrl+C to stop")
    
    try:
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        print("\n🛑 Stopping mock server...")
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
