import argschema
from argschema.fields import Boolean, Str
from EMaligner.EM_aligner_python_schema import EMA_Schema


class EMA_Output_Schema(argschema.schemas.DefaultSchema):
    stack = argschema.fields.Str(required=True)
    backup_stack = argschema.fields.List(Str, required=True)

class EMA_Input_Schema(EMA_Schema):
    clone_section = Boolean(
        required=False,
        default=False,
        missing=False,
        description="If z already exists in output stack copy it to a backup stack")
    overwrite_z = Boolean(
        required=False,
        default=True,
        missing=True,
        description="Overwrite existing tilespecs if section already exists")


__all__ = ["EMA_Schema", "EMA_Output_Schema"]
