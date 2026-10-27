from pydantic import BaseModel


class AgentConfigResponse(BaseModel):
    id: str
    name: str
    tagline: str
