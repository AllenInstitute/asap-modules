Lens Correction
=================

##  [lens_correction.py](lens_correction.py)
Script to call TrakEM2 lens correction estimator.

input json:
```JSON
{
            "required": [
                "fiji_path",
                "grid_size",
                "manifest_path",
                "project_path"
            ],
            "type": "object",
            "properties": {
                "fiji_path": {
                    "type": "string",
                    "description": "path to FIJI"
                },
                "log_level": {
                    "default": "ERROR",
                    "type": "string"
                },
                "grid_size": {
                    "type": "integer",
                    "description": "maximum row and column to form square subset of tiles starting from zero (based on filenames which end in \"\\{row\\}_\\{column\\}.tif\")",
                    "format": "int32"
                },
                "project_path": {
                    "type": "string",
                    "description": "path to project directory"
                },
                "input_json": {
                    "type": "string"
                },
                "align_params": {
                    "required": [
                        "clearTransform",
                        "desiredModelIndex",
                        "dimension",
                        "expectedModelIndex",
                        "identityTolerance",
                        "lambdaVal",
                        "maxEpsilon",
                        "maxIterationsOptimize",
                        "maxPlateauWidthOptimize",
                        "minInlierRatio",
                        "minNumInliers",
                        "multipleHypotheses",
                        "regularize",
                        "rejectIdentity",
                        "rod",
                        "tilesAreInPlace",
                        "visualize"
                    ],
                    "type": "object",
                    "properties": {
                        "regularize": {
                            "type": "boolean",
                            "description": "Whether to regularize the desired model with the regularizer model by lambda"
                        },
                        "expectedModelIndex": {
                            "type": "integer",
                            "description": "expected model for RANSAC filtering, 0=Translation, 1=\"Rigid\", 2=\"Similarity\", 3=\"Affine\"",
                            "format": "int32"
                        },
                        "maxIterationsOptimize": {
                            "type": "integer",
                            "description": "Max number of iterations for optimizer",
                            "format": "int32"
                        },
                        "lambdaVal": {
                            "type": "number",
                            "description": "Lambda parameter by which the regularizer model affects fitting of the desired model",
                            "format": "float"
                        },
                        "rod": {
                            "type": "number",
                            "description": "ratio of distances for matching SIFT features",
                            "format": "float"
                        },
                        "maxEpsilon": {
                            "type": "number",
                            "description": "maximum acceptable epsilon for RANSAC filtering",
                            "format": "float"
                        },
                        "tilesAreInPlace": {
                            "type": "boolean",
                            "description": "Whether tile inputs to TrakEM2 are in place to be compared only to neighboring tiles."
                        },
                        "identityTolerance": {
                            "type": "number",
                            "description": "Tolerance to which Identity should rejected, in pixels",
                            "format": "float"
                        },
                        "rejectIdentity": {
                            "type": "boolean",
                            "description": "Reject Identity model (constant background) up to a tolerance defined by identityTolerance"
                        },
                        "visualize": {
                            "type": "boolean",
                            "description": "Whether to have TrakEM2 visualize the lens correction transform.  Not recommended when running through xvfb"
                        },
                        "minInlierRatio": {
                            "type": "number",
                            "description": "minimum inlier ratio for RANSAC filtering",
                            "format": "float"
                        },
                        "minNumInliers": {
                            "type": "integer",
                            "description": "minimum number of inliers for RANSAC filtering",
                            "format": "int32"
                        },
                        "desiredModelIndex": {
                            "type": "integer",
                            "description": "Affine homography model which optimization will try to fit, 0=\"Translation\", 1=\"Rigid\", 2=\"Similarity\", 3=\"Affine\"",
                            "format": "int32"
                        },
                        "multipleHypotheses": {
                            "type": "boolean",
                            "description": "Utilize RANSAC filtering which allows fitting multiple hypothesis models"
                        },
                        "dimension": {
                            "type": "integer",
                            "description": "Dimension of polynomial kernel to fit for distortion model",
                            "format": "int32"
                        },
                        "maxPlateauWidthOptimize": {
                            "type": "integer",
                            "description": "Maximum plateau width for optimizer",
                            "format": "int32"
                        },
                        "clearTransform": {
                            "type": "boolean",
                            "description": "Whether to remove transforms from tiles before SIFT matching.  Not recommended"
                        }
                    }
                },
                "manifest_path": {
                    "type": "string",
                    "description": "path to manifest file"
                },
                "output_json": {
                    "type": "string"
                },
                "SIFT_params": {
                    "required": [
                        "fdBins",
                        "fdSize",
                        "initialSigma",
                        "maxOctaveSize",
                        "minOctaveSize",
                        "steps"
                    ],
                    "type": "object",
                    "properties": {
                        "initialSigma": {
                            "type": "number",
                            "description": "initial sigma value for SIFT's gaussian blur, in pixels",
                            "format": "float"
                        },
                        "fdBins": {
                            "type": "integer",
                            "description": "SIFT feature descriptor orientation bins",
                            "format": "int32"
                        },
                        "maxOctaveSize": {
                            "type": "integer",
                            "description": "maximum image size used for SIFT octave, in pixels",
                            "format": "int32"
                        },
                        "steps": {
                            "type": "integer",
                            "description": "steps per SIFT scale octave",
                            "format": "int32"
                        },
                        "minOctaveSize": {
                            "type": "integer",
                            "description": "minimum image size used for SIFT octave, in pixels",
                            "format": "int32"
                        },
                        "fdSize": {
                            "type": "integer",
                            "description": "SIFT feature descriptor size",
                            "format": "int32"
                        }
                    }
                }
            }}
```

output json:
```JSON
{
            "required": [
                "output_json"
            ],
            "type": "object",
            "properties": {
                "output_json": {
                    "type": "string",
                    "description": "path to file "
                }
            }
        }
```

## [apply_lens_correction.py](apply_lens_correction.py)
Script to read tilespecs from a set of z values in a render stack, prepend the supplied local transformation, and upload to an output render stack.

input json:
```JSON
{
            "required": [
                "inputStack",
                "outputStack",
                "refId",
                "zs"
            ],
            "type": "object",
            "properties": {
                "log_level": {
                    "default": "ERROR",
                    "type": "string"
                },
                "render": {
                    "required": [
                        "client_scripts",
                        "host",
                        "owner",
                        "port",
                        "project"
                    ],
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "render default project"
                        },
                        "host": {
                            "type": "string",
                            "description": "render host"
                        },
                        "memGB": {
                            "default": "5G",
                            "type": "string",
                            "description": "string describing java heap memory (default 5G)"
                        },
                        "owner": {
                            "type": "string",
                            "description": "render default owner"
                        },
                        "port": {
                            "type": "integer",
                            "description": "render post integer",
                            "format": "int32"
                        },
                        "client_scripts": {
                            "type": "string",
                            "description": "path to render client scripts"
                        }
                    }
                },
                "transform": {
                    "required": [
                        "className",
                        "dataString",
                        "type"
                    ],
                    "type": "object",
                    "properties": {
                        "className": {
                            "type": "string",
                            "description": "mpicbg-compatible className"
                        },
                        "dataString": {
                            "type": "string",
                            "description": "mpicbg-compatible dataString"
                        },
                        "type": {
                            "type": "string",
                            "description": "Transform type as defined in Render Transform Spec.  This module currently expects a \"leaf\""
                        }
                    }
                },
                "inputStack": {
                    "type": "string",
                    "description": "Render Stack with tiles that should be transformed"
                },
                "input_json": {
                    "type": "string"
                },
                "outputStack": {
                    "type": "string",
                    "description": "Render Stack to which transformed tiles will be added"
                },
                "output_json": {
                    "type": "string"
                },
                "refId": {
                    "x-nullable": true,
                    "type": "string",
                    "description": "Reference ID to use when uploading transform to render database (Not Implemented)"
                },
                "zs": {
                    "items": {
                        "type": "integer",
                        "format": "int32"
                    },
                    "type": "array",
                    "description": "z indices to which transform should be prepended"
                }
            }
        }
```

output json:
```JSON
{
            "required": [
                "refId",
                "stack"
            ],
            "type": "object",
            "properties": {
                "stack": {
                    "type": "string",
                    "description": "stack to which transformed tiles were written"
                },
                "refId": {
                    "type": "string",
                    "description": "unique identifier string used as reference ID"
                }
            }
        }
```

## [run_lens_correction.bsh](run_lens_correction.bsh)
beanshell script which can be interpreted by TrakEM2 to perform estimaation of lens correction from a set of highly overlapping tiles.  This script is called via a subprocess command to a headless (via xvfb) ImageJ script in [lens_correction.py](lens_correction.py).
