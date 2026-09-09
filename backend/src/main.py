"""This is the entry point of the code the backend which will be running using uvicorn 
using fastapi endpoints """

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.modules.auth.router import router as auth_router

app = FastAPI(
    title="SentinelLog-AI API",
    description="Backend API for SentinelLog-AI",
    version="1.0.0"
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)

@app.get("/")
def root():
    return {"message": "Welcome to SentinelLog-AI API"}
