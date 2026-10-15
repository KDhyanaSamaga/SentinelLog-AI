from pydantic import BaseModel

class ModelInput(BaseModel):
    """This is used to validate the incomming logs in the following formate before giving it to the ML model
    'Content': ['PacketResponder 1 for block blk_38865049 terminating'],
    'Component': ['dfs.DataNode$PacketResponder'],
    'Hour': [20],
    'Minute': [36],
    'Second': [15],
    'Time_gap': [0.0],
    'Pid_freq': [1]
    """
    content: str
    component: str
    hour: int
    minute: int
    second: int
    time_gap: float
    pid_freq: int

class ModelOutput(BaseModel):
    """The model recives the input from the ModelInput the model perform the prediction and then returns as """
    
