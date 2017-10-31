import mm
import argschema
from argschema.fields import Str, Nested


class Transform(argschema.schemas.DefaultSchema):
    className = Str(required=True)
    dataString = Str(required=True)
    type = Str(validator=mm.validate.OneOf(['leaf']), required=True)
    # type_ = OptionList(options=['leaf'], required=True)


class Stack(argschema.schemas.DefaultSchema):
    stack = Str(required=True)
    transform = Nested(Transform, required=False)
    children = Nested("self", many=True)
