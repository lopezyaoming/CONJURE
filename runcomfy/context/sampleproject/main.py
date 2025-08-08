from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from contextlib import asynccontextmanager
import uvicorn
from pathlib import Path
from loguru import logger
import os
import time
from dotenv import load_dotenv
import json
from concurrent.futures import ThreadPoolExecutor
import logging

from .routes import include_routes, router
from .runcomfy_routes import runcomfy_router
from .utils import setup_logging, cleanup_temp_files, FileManager
from .services import ComfyUIService
from .gemini_service import GeminiService

# Load environment variables
load_dotenv()

# Configuration
class Settings:
    """Application settings"""
    
    def __init__(self):
        self.app_name = "forMat Backend"
        self.app_version = "1.0.0"
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))
        self.allowed_hosts = os.getenv("ALLOWED_HOSTS", "*").split(",")
        self.cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
        self.max_upload_size = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB
        
        # ComfyUI Mode (local or cloud)
        self.comfyui_mode = os.getenv("COMFYUI_MODE", "cloud").lower()
        
        # Local ComfyUI settings
        self.comfyui_url = os.getenv("COMFYUI_URL", "http://localhost:8188")
        self.comfyui_api_key = os.getenv("COMFYUI_API_KEY", "")
        
        # RunComfy cloud settings
        self.runcomfy_api_base_url = os.getenv("RUNCOMFY_API_BASE_URL", "https://api.runcomfy.net")
        self.runcomfy_user_id = os.getenv("RUNCOMFY_USER_ID", "92b6028c-6a08-4571-a998-0f2d66493db1")
        self.runcomfy_api_token = os.getenv("RUNCOMFY_API_TOKEN", "f706b389-2346-4a03-a0ec-7aff43f8ddfd")
        
        # RunComfy machine configuration
        self.runcomfy_default_server_type = os.getenv("RUNCOMFY_DEFAULT_SERVER_TYPE", "medium")
        self.runcomfy_default_duration = int(os.getenv("RUNCOMFY_DEFAULT_DURATION", "3600"))
        self.runcomfy_auto_shutdown = os.getenv("RUNCOMFY_AUTO_SHUTDOWN", "true").lower() == "true"
        self.runcomfy_machine_reuse = os.getenv("RUNCOMFY_MACHINE_REUSE", "true").lower() == "true"
        self.runcomfy_idle_timeout = int(os.getenv("RUNCOMFY_IDLE_TIMEOUT", "300"))
        
        # RunComfy timeouts and limits
        self.runcomfy_max_retries = int(os.getenv("RUNCOMFY_MAX_RETRIES", "3"))
        self.runcomfy_poll_interval = int(os.getenv("RUNCOMFY_POLL_INTERVAL", "5"))
        self.runcomfy_machine_timeout = int(os.getenv("RUNCOMFY_MACHINE_TIMEOUT", "600"))
        
        # ComfyUI workflow execution
        self.comfyui_execution_timeout = int(os.getenv("COMFYUI_EXECUTION_TIMEOUT", "2000"))  # 33 minutes for model loading
        self.comfyui_poll_interval = int(os.getenv("COMFYUI_POLL_INTERVAL", "3"))
        
        # OpenAI settings for Griptape
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # Gemini settings for Google AI
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        # File storage settings
        self.data_dir = Path(os.getenv("DATA_DIR", "backend/data"))
        self.workflows_dir = Path(os.getenv("WORKFLOWS_DIR", "backend/workflows"))
        
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)

settings = Settings()

# Performance optimizations
from functools import lru_cache
import hashlib

# Global thread pool for CPU-intensive tasks
thread_pool = ThreadPoolExecutor(max_workers=4)

# Simple in-memory cache
cache = {}

@lru_cache(maxsize=100)
def get_cached_workflow(workflow_path: str):
    """Cache workflow files to avoid repeated disk reads"""
    with open(workflow_path, 'r') as f:
        return json.load(f)

def get_cache_key(*args):
    """Generate cache key from arguments"""
    return hashlib.md5(str(args).encode()).hexdigest()

# Startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifecycle events"""
    
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Data directory: {settings.data_dir}")
    
    # Verify required directories exist
    required_dirs = [
        settings.data_dir / "input",
        settings.data_dir / "output", 
        settings.workflows_dir
    ]
    
    for dir_path in required_dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Verified directory: {dir_path}")
    
    # Check ComfyUI connection based on mode
    logger.info(f"🎨 ComfyUI Mode: {settings.comfyui_mode.upper()}")
    
    if settings.comfyui_mode == "cloud":
        # Check RunComfy API credentials
        if settings.runcomfy_api_token:
            logger.info("✅ RunComfy API token configured")
            logger.info(f"   User ID: {settings.runcomfy_user_id}")
            logger.info(f"   Base URL: {settings.runcomfy_api_base_url}")
        else:
            logger.warning("⚠️  RUNCOMFY_API_TOKEN not set - RunComfy features will be unavailable")
    else:
        # Check local ComfyUI connection
        try:
            import requests
            response = requests.get(
                f"{settings.comfyui_url}/object_info",
                headers={"Authorization": f"Bearer {settings.comfyui_api_key}"} if settings.comfyui_api_key else {},
                timeout=10
            )
            if response.status_code == 200:
                logger.info("✅ Local ComfyUI connection verified")
            else:
                logger.warning("⚠️  Local ComfyUI responded with non-200 status")
        except Exception as e:
            logger.warning(f"⚠️  Could not connect to local ComfyUI: {e}")
            logger.info("Local ComfyUI integration will be available when server is running")
    
    # Check OpenAI API key for Griptape
    if settings.openai_api_key:
        logger.info("✅ OpenAI API key configured for Griptape")
    else:
        logger.warning("⚠️  OpenAI API key not set - Griptape will use fallback templates")
    
    # Check Gemini API key for Google AI
    if settings.gemini_api_key:
        logger.info("✅ Gemini API key configured for Google AI")
    else:
        logger.warning("⚠️  Gemini API key not set - Google AI features will be unavailable")
    
    logger.info("🚀 forMat backend started successfully")
    
    # Singletons and Dependencies
    file_manager = FileManager(base_dir=Path(os.getenv("DATA_DIR", "backend/data")))

    comfyui_service = ComfyUIService(
        file_manager=file_manager,
        workflow_path=os.getenv("WORKFLOW_FILE", "backend/workflows/user2imgs.json")
    )

    gemini_service = GeminiService()
    
    # Pass singletons to the router/dependencies
    app.state.file_manager = file_manager
    app.state.comfyui_service = comfyui_service
    app.state.gemini_service = gemini_service
    
    yield
    
    # Shutdown
    logger.info("Shutting down forMat backend...")
    
    # Cleanup temporary files
    try:
        cleanup_temp_files()
        logger.info("✅ Cleanup completed")
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
    
    logger.info("👋 forMat backend stopped")
    thread_pool.shutdown(wait=True)

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    **forMat Backend API**
    
    Transform raw construction materials into buildable designs using AI.
    
    ## Features
    
    - 📸 **Material Upload**: Upload photos of raw materials
    - 🎨 **Design Generation**: AI-powered design variants using ComfyUI
    - 🏗️ **3D Models**: Generate .glb models with structural optimization
    - 📋 **Instructions**: Detailed fabrication guides using Griptape AI
    - 📊 **Progress Tracking**: Real-time job status and progress
    
    ## Workflow
    
    1. **Upload** material image with design prompt
    2. **Generate** 3 design variants using ComfyUI
    3. **Select** preferred variant
    4. **Receive** 3D models, assembly diagrams, and fabrication instructions
    
    ## Integration
    
    - **ComfyUI**: Image-to-design and 3D generation workflows
    - **Griptape**: AI-powered instruction generation
    - **Hunyuan3D**: Multiview-to-3D model generation
    - **Karamba**: Structural optimization (planned)
    """,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

# CORS Middleware - Must be before routing
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://10.1.10.31:3000",
        "http://10.1.10.31:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the output directory using an absolute path from the current working directory.
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

current_working_directory = Path(os.getcwd())
static_files_path = current_working_directory / "data" / "output"
static_files_path.mkdir(parents=True, exist_ok=True)
app.mount("/output", StaticFiles(directory=static_files_path), name="output")

from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from starlette.types import Scope, Receive, Send

class NoCacheStaticFiles(StaticFiles):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Add no-cache headers to static file responses"""
        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"].extend([
                    (b"Cache-Control", b"no-cache, no-store, must-revalidate"),
                    (b"Pragma", b"no-cache"),
                    (b"Expires", b"0"),
                ])
            await send(message)
        await super().__call__(scope, receive, wrapped_send)

# Mount assets directory for static files like images
assets_path = current_working_directory / "assets"
assets_path.mkdir(parents=True, exist_ok=True)
app.mount("/assets", NoCacheStaticFiles(directory=str(assets_path)), name="assets")

print("STATIC FILES SERVED FROM:", static_files_path.resolve())
print("ASSETS SERVED FROM:", assets_path.resolve())

# Add middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts
)

# Custom middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests"""
    start_time = time.time()
    
    # Skip logging for health checks and static files
    skip_paths = ["/health", "/docs", "/redoc", "/openapi.json"]
    should_log = not any(request.url.path.startswith(path) for path in skip_paths)
    
    if should_log:
        logger.info(f"📨 {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    if should_log:
        process_time = time.time() - start_time
        logger.info(f"📤 {response.status_code} {request.url.path} ({process_time:.3f}s)")
    
    return response

# Mount static files for serving frontend (if needed)
if Path("frontend").exists():
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Include API routes
include_routes(app)

# Include the API router
app.include_router(router)

# Include RunComfy-specific routes
app.include_router(runcomfy_router)

# Root endpoint
@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with API information"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{settings.app_name}</title>
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 800px; 
                margin: 0 auto; 
                padding: 40px 20px;
                background: #f8f9fa;
                color: #333;
            }}
            .header {{ 
                text-align: center; 
                margin-bottom: 40px;
                padding: 20px;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .status {{ 
                background: #d4edda; 
                padding: 15px; 
                border-radius: 5px; 
                margin: 20px 0;
                border-left: 4px solid #28a745;
            }}
            .endpoints {{ 
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .endpoint {{ 
                margin: 15px 0; 
                padding: 10px;
                background: #f8f9fa;
                border-radius: 4px;
                font-family: monospace;
            }}
            .method {{ 
                display: inline-block;
                padding: 2px 8px;
                border-radius: 3px;
                font-weight: bold;
                margin-right: 10px;
                font-size: 12px;
            }}
            .post {{ background: #28a745; color: white; }}
            .get {{ background: #007bff; color: white; }}
            .delete {{ background: #dc3545; color: white; }}
            a {{ color: #007bff; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🏗️ {settings.app_name}</h1>
            <p>AI-Powered Circular Design Platform</p>
            <p>Version {settings.app_version}</p>
        </div>
        
        <div class="status">
            <strong>✅ Server Status:</strong> Running<br>
            <strong>🎨 ComfyUI Mode:</strong> {settings.comfyui_mode.upper()}<br>
            {'<strong>☁️ RunComfy URL:</strong> ' + settings.runcomfy_api_base_url + '<br>' if settings.comfyui_mode == 'cloud' else '<strong>🏠 Local ComfyUI:</strong> ' + settings.comfyui_url + '<br>'}
            <strong>📁 Data Directory:</strong> {settings.data_dir}<br>
            <strong>🤖 Griptape:</strong> {'Configured' if settings.openai_api_key else 'Fallback mode'}
        </div>
        
        <div class="endpoints">
            <h2>🔌 API Endpoints</h2>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <strong>/api/upload</strong> - Upload material image and start design generation
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <strong>/api/jobs/{{job_id}}/status</strong> - Check job status and get variants
            </div>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <strong>/api/jobs/{{job_id}}/variants/{{variant_id}}/select</strong> - Select variant and generate details
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <strong>/api/files/jobs/{{job_id}}/models/{{model_name}}</strong> - Download 3D models
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <strong>/api/health</strong> - Health check
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <strong>/api/system/status</strong> - System status and metrics
            </div>
        </div>
        
        <div style="margin-top: 40px; text-align: center; color: #666;">
            <p>
                {'<a href="/docs">📚 API Documentation</a>' if settings.debug else 'API Documentation available in debug mode'}
                {'<br><a href="/redoc">📖 ReDoc Documentation</a>' if settings.debug else ''}
            </p>
            <p><small>Built with FastAPI, ComfyUI, and Griptape</small></p>
        </div>
    </body>
    </html>
    """

# Set up error logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
frontend_error_log = log_dir / "frontend_errors.log"
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(frontend_error_log, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Custom error handler for static files and API
from fastapi.responses import JSONResponse
from fastapi import status

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    error_message = f"{request.method} {request.url.path} - {type(exc).__name__}: {exc}"
    logging.error(error_message)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "error": str(exc)}
    )

# Endpoint to view the last 10 frontend errors
@app.get("/logs/frontend-errors")
def get_frontend_errors():
    try:
        with open(frontend_error_log, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # Get last 10 error lines
        last_errors = lines[-10:] if len(lines) > 10 else lines
        return {"last_errors": last_errors}
    except Exception as e:
        return {"error": str(e)}

# Run server function
def start_server():
    """Start the FastAPI server"""
    import time
    
    logger.info(f"🚀 Starting {settings.app_name} on {settings.host}:{settings.port}")
    
    # Configure uvicorn
    config = uvicorn.Config(
        app=app,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug",
        access_log=settings.debug,
        loop="asyncio"
    )
    
    server = uvicorn.Server(config)
    
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("⏹️  Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")

if __name__ == "__main__":
    # Import here to avoid issues with imports
    import time
    from fastapi.responses import JSONResponse
    
    start_server()
