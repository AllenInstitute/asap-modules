import argschema


class RenderClientParameters(argschema.schemas.DefaultSchema):
    host = argschema.fields.Str(
        required=True, description='render host')
    port = argschema.fields.Int(
        required=True, description='render post integer')
    owner = argschema.fields.Str(
        required=True, description='render default owner')
    project = argschema.fields.Str(
        required=True, description='render default project')
    client_scripts = argschema.fields.Str(
        required=True, description='path to render client scripts')
    memGB = argschema.fields.Str(
        required=False, default='5G',
        description='string describing java heap memory (default 5G)')


class RenderParameters(argschema.ArgSchema):
    render = argschema.fields.Nested(
        RenderClientParameters,
        required=True,
        description="parameters to connect to render server")


class TemplateParameters(RenderParameters):
    example = argschema.fields.Str(required=True,
                                   description='an example')
    default_val = argschema.fields.Str(required=False, default="a default value",
                                       description='an example with a default')


class TemplateOutputParameters(argschema.schemas.DefaultSchema):
    output_value = argschema.fields.Str(required=True,
                                        description="an output of the module")
