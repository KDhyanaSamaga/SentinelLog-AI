import joblib
import logging
from app.core.config import Settings

from fastapi import APIRouter,HTTPException,status

from app.modules.aiModel.schemas import ModelInput

logger = logging.getLogger(__name__)

settings = Settings()

router = APIRouter(prefix="/model",tags=["AI-Model"])
model_path = r'D:\SentinelLog-AI\backend\app\modules\aiModel\hdfs_log_classifier.joblib'
model = joblib.load(model_path)

@router.post('/log')
def get_log():
    """This is to get the input log from the stream via frontent the log must be in the formate after processing 
    'Content': ['PacketResponder 1 for block blk_38865049 terminating'],
    'Component': ['dfs.DataNode$PacketResponder'],
    'Hour': [20],
    'Minute': [36],
    'Second': [15],
    'Time_gap': [0.0],
    'Pid_freq': [1]
    this is the input formate check this class via schema and modify against this from the schema
    """

    return

