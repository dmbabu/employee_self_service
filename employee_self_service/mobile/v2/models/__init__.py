from pydantic import BaseModel
from typing import List, Optional

class LoginModel(BaseModel):
    usr: str
    pwd: str