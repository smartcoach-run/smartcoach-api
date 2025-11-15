from fastapi import FastAPI
from pydantic import BaseModel
import main

app = FastAPI()

class Req(BaseModel):
    id: str

@app.post("/generate_by_id")
def generate_by_id(req: Req):
    return main.generate_by_id(req.id)