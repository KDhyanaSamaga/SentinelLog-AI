# Step 1: Import the necessory modules
from fastapi import FastAPI
from fastapi import HTTPException

from dotenv import load_dotenv
import os

from huggingface_hub import InferenceClient

from schemas import LogAnalysisRequest,LLMOutput
from promt import prompt

# Step 2: Create a router with its own name to uniquely identlify it
app = FastAPI(title="AI-LLM Service")

# Step 3: Create the following API Endpoints

@app.get('/health')
async def health_check():
    """This endpoint is an internal endpoint, This endpoint helps to check wether the provided 
    API Key and other credintials are working fine or not """

    if not os.getenv("HUGGINGFACE_API_KEY"):
        raise HTTPException(status_code=500,detail="The system failed to connect with the provided KEY")

    try:
        client = InferenceClient(
            model="Qwen/Qwen2.5-72B-Instruct", token=os.getenv("HF_TOKEN")
        )

        response =  client.chat.completions(
            {"role": "user", "content": "ping"},
            max_tokens = 5
        )
        return{
            "status": "success",
            "message": "LLM connection active and verified.",
        }
    except Exception as e:
        raise HTTPException(
            status_code= 502,
            detail= f"LLM connection failed: {str(e)}"
        )

@app.post('/analyze')
async def analyze_log(payload: LogAnalysisRequest):
    try:
        client = InferenceClient(
                    model="Qwen/Qwen2.5-72B-Instruct",
                    token=os.getenv("HF_TOKEN")
                )
        response = client.chat.completions.create(
            messages=[
                { 
                    "role": "system", 
                    "content": ( "You are a senior cybersecurity expert. " "Analyze security logs accurately and concisely." )
                }, 
                { 
                    "role": "user", 
                    "content": prompt(payload) 
                }
            ],
            temperature = 0.3,
            max_tokens =  600
        )

        message = response.choices[0].message.content.strip()

        return LLMOutput(message=message)

    except Exception as e:
        raise HTTPException(
            status_code = 500,
            detail = f"Failed to process {e}"
        )