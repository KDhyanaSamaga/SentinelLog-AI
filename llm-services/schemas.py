from pydantic import BaseModel

class LogAnalysisRequest(BaseModel):
    raw_log: str
    log_type: str  # 'warn' or 'normal'
    machine: str  # 'HDFS', 'BGL', etc.
    extra_context: str | None = None

class LLMOutput(BaseModel):
    message:str