import argschema
from EMaligner.EM_aligner_python_schema import EMA_Schema


class EMA_Output_Schema(argschema.schemas.DefaultSchema):
    stack = argschema.fields.Str(required=True)


__all__ = ["EMA_Schema", "EMA_Output_Schema"]
