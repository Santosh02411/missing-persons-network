from pydantic import BaseModel


class EmergencyContact(BaseModel):
    label: str
    number: str
    description: str
