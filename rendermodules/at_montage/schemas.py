from ..module.render_module import RenderModule, RenderParameters
from argschema.fields import InputFile, InputDir, Str, Float, Int, OutputDir
from argschema.schemas import DefaultSchema

class CreateMontagePointMatchParameters(RenderParameters):
    stack = Str(required=True,
        description='stack to take stitching from')
    matchCollection = Str(required=True,
        description='collection to save to')
    minZ = Int(required=False,
        description='min Z to consider')
    maxZ = Int(required=False,
        description='min Z to consider (default min in stack)')
    dataRoot = OutputDir(required = True,
        description='max Z to consider (default max in stack)')
    delta = Int(required=False,default=150,
        metadata ={'description':'number of pixels between artificial matches'})
    pool_size = Int(required=False,default=20,
        description='number of parallel processes (default 20)')

class CreateMontagePointMatchOutputParameters(DefaultSchema):
    output_value = Str(required=True,description= "an output of the module")

class ATMontageParams(RenderParameters):
    stitching_json = Str(required=True,
                       description='Input Json file location')
    jar_file = Str(required=True,
                      description='Jar file path')
    baseDataUrl = Str(required=True,
                      description='Base Data Url')
    stack = Str(required=True,
                      description='Input Stack')
    outputStack = Str(required=True,
                      description='Output Stack')
    section = Float(required=True,
                      description='Section z')
    maxEpsilon = Float(required=False, default=2.5,
                      description='Max Epsilon')
    initialSigma = Float(required=False, default=1.6,
                      description='initial Sigma')
    percentSaturated = Float(required=False, default=0.9,
                      description='Percent Saturated')
    modelType = Int(required=False, default=1,
                      description='Model Type')
    steps = Int(required=False, default=3,
                      description='Number of steps for SIFT')
