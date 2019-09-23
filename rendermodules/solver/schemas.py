import argschema
from bigfeta.schemas import BigFetaSchema


class BigFetaOutputSchema(argschema.schemas.DefaultSchema):
    stack = argschema.fields.Str(required=True)


__all__ = ["BigFetaSchema", "BigFetaOutputSchema"]
