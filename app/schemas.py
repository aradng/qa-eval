from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

from app.config import get_config


class Operator(StrEnum):
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"


class Total(BaseModel):
    kind: Literal["total"]
    name: str = Field(validation_alias="product_name")


class Constant(BaseModel):
    kind: Literal["constant"]
    value: float = Field(gt=0)


class Binary(BaseModel):
    kind: Literal["binary"]
    op: Operator
    children: list["Query"]


Query = Annotated[
    Union[Total, Constant, Binary], Field(discriminator="kind")
]

Binary.model_rebuild()

QUERY = TypeAdapter(Query)

# Computed once, at import time. Validation mode, so the schema describes what
# the endpoint accepts. SCHEMA_DOC_MODE switches it to the serialization view,
# which is what you want when the same schema documents responses.
SCHEMA = QUERY.json_schema(
    mode="serialization"
    if get_config().SCHEMA_DOC_MODE
    else "validation"
)
