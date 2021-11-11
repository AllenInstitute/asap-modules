import warnings

from marshmallow import ValidationError, validate, post_load, pre_load
import argschema

from asap.module.schemas import RenderParameters


class OverridableParameterSchema(argschema.schemas.DefaultSchema):
    @pre_load
    def override_input(self, data):
        return self._override_input(data)

    def _override_input(self, data):
        pass

    @staticmethod
    def fix_badkey(data, badkey, goodkey):
        if badkey in data:
            warnings.warn(
                "{b} variable has been deprecated. Will try to fill in "
                "{g} if empty.".format(b=badkey, g=goodkey),
                DeprecationWarning)
            data[goodkey] = (
                data[goodkey] if (goodkey in data) else data[badkey])


class ProcessPoolParameters(argschema.schemas.DefaultSchema):
    pool_size = argschema.fields.Int(required=False, default=1)


class ZValueParameters(OverridableParameterSchema):
    """template schema which interprets z values on which to act
    assumes a hierarchy such that minZ, maxZ are
    superceded by z which is superceded by zValues.
    """
    minZ = argschema.fields.Int(required=False)
    maxZ = argschema.fields.Int(required=False)
    z = argschema.fields.Int(required=False)
    zValues = argschema.fields.List(
            argschema.fields.Int,
            cli_as_single_argument=True,
            required=False)

    @post_load
    def generate_zValues(self, data):
        return self._generate_zValues(data)

    def _generate_zValues(self, data):
        if 'zValues' in data:
            return
        elif 'z' in data:
            data['zValues'] = [data['z']]
        elif ('minZ' in data) and ('maxZ' in data):
            data['zValues'] = range(data['minZ'], data['maxZ'] + 1)
        else:
            raise ValidationError("no z values specified")

    def _override_input(self, data):
        super(ZValueParameters, self)._override_input(data)
        # DEPRECATED
        # the following overrides should be removed in future versions
        self.fix_badkey(data, 'z_index', 'z')
        self.fix_badkey(data, 'zstart', 'minZ')
        self.fix_badkey(data, 'zend', 'maxZ')
        self.fix_badkey(data, 'zs', 'zValues')


class RenderMipMapPathBuilder(argschema.schemas.DefaultSchema):
    rootPath = argschema.fields.Str(required=False)
    numberOfLevels = argschema.fields.Int(required=False)
    extension = argschema.fields.Str(
        required=False, validator=validate.OneOf(['png', 'jpg', 'tif']))


class RenderCycle(argschema.schemas.DefaultSchema):
    number = argschema.fields.Int(required=False)
    stepNumber = argschema.fields.Int(required=False)


class RenderStackVersion(argschema.schemas.DefaultSchema):
    createTimestamp = argschema.fields.Str(required=False)  # TODO DateTime
    versionNotes = argschema.fields.Str(required=False)
    cycleNumber = argschema.fields.Int(required=False)
    cycleStepNumber = argschema.fields.Int(required=False)
    stackResolutionX = argschema.fields.Float(required=False)
    stackResolutionY = argschema.fields.Float(required=False)
    stackResolutionZ = argschema.fields.Float(required=False)
    materializedBoxRootPath = argschema.fields.Str(required=False)
    mipmapPathBuilder = argschema.fields.Nested(RenderMipMapPathBuilder,
                                                required=False)
    cycle = argschema.fields.Nested(RenderCycle, required=False)
    stackResolutionValues = argschema.fields.List(
            argschema.fields.Int,
            cli_as_single_argument=True,
            required=False)


class OutputStackParameters(RenderParameters, ZValueParameters,
                            ProcessPoolParameters, OverridableParameterSchema):
    """template schema for writing tilespecs to an output stack"""
    output_stack = argschema.fields.Str(required=True)
    close_stack = argschema.fields.Boolean(required=False, default=False)
    overwrite_zlayer = argschema.fields.Boolean(required=False, default=False)
    output_stackVersion = argschema.fields.Nested(
        RenderStackVersion, required=False)

    def _override_input(self, data):
        super(OutputStackParameters, self)._override_input(data)
        # DEPRECATED
        # the following overrides should be removed in future versions
        self.fix_badkey(data, 'stack', 'output_stack')
        self.fix_badkey(data, 'outputStack', 'output_stack')


class InputStackParameters(RenderParameters, ZValueParameters,
                           OverridableParameterSchema):
    """template schema for schemas which take input from a stack
    """
    input_stack = argschema.fields.Str(required=True)

    def _override_input(self, data):
        super(InputStackParameters, self)._override_input(data)
        # DEPRECATED
        # the following overrides should be removed in future versions
        self.fix_badkey(data, 'stack', 'input_stack')
        self.fix_badkey(data, 'inputStack', 'input_stack')


class StackTransitionParameters(OutputStackParameters, InputStackParameters):
    """template schema for schemas which take input from one stack, perform
    (mostly render-python based) operations on tiles from that stack,
    and output tiles to another stack.
    """
    def _override_input(self, data):
        if 'stack' in data:
            raise ValidationError(
                "key 'stack' is ambiguous please specify "
                "input_stack or output_stack")
        super(StackTransitionParameters, self)._override_input(data)
