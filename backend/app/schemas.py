from pydantic import BaseModel, Field


class ConvertRequest(BaseModel):
    document_id: str
    format: str = Field(..., description="IEEE, ACM, Springer, APA, or MLA")


class PreviewRequest(BaseModel):
    document_id: str


class ExportRequest(BaseModel):
    document_id: str
    export_format: str = Field(..., pattern="^(pdf|docx)$")


class AiSuggestionsRequest(BaseModel):
    document_id: str
    format: str = "IEEE"
