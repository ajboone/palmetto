from pydantic import BaseModel, Field, field_validator


class AgentQuery(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must not be blank")
        return value


class AgentResponse(BaseModel):
    answer: str
    tools_used: list[str]
    tool_call_count: int
    model: str
    limitations: list[str] = Field(default_factory=list)


class AgentToolTrace(BaseModel):
    tool_name: str
    success: bool