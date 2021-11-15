Data Import
=================

## [generate_EM_tilespecs_from_metafile.py](generate_EM_tilespecs_from_metafile.py)

Use metadata file (json starting with `_metadata_`) produced by pyTEMCA to upload stage-coordinate tilespecs to a new or existing stack.

input json:
```JSON
{
    "required": [
        "metafile",
        "stack",
        "z_index"
    ],
    "type": "object",
    "properties": {
        "image_directory": {
            "type": "string",
            "description": "directory used in determining absolute paths to images. Defaults to parent directory containing metafile if omitted."
        },
        "close_stack": {
            "default": false,
            "type": "boolean",
            "description": "whether to set stack to 'COMPLETE' after performing operation"
        },
        "minimum_intensity": {
            "default": 0,
            "type": "integer",
            "description": "intensity value to interpret as black",
            "format": "int32"
        },
        "z_index": {
            "type": "integer",
            "description": "z value to which tilespecs from ROI will be added",
            "format": "int32"
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
        "sectionId": {
            "type": "string",
            "description": "sectionId to apply to tiles during ingest.  If unspecified will default to a string representation of the float value of z_index."
        },
        "metafile": {
            "type": "string",
            "description": "metadata file containing TEMCA acquisition data"
        },
        "pool_size": {
            "default": 1,
            "type": "integer",
            "description": "processes to spawn for parallelization",
            "format": "int32"
        },
        "maximum_intensity": {
            "default": 255,
            "type": "integer",
            "description": "intensity value to interpret as white",
            "format": "int32"
        },
        "overwrite_zlayer": {
            "default": false,
            "type": "boolean",
            "description": "whether to remove the existing layer from the target stack before uploading."
        },
        "log_level": {
            "default": "ERROR",
            "type": "string"
        },
        "output_json": {
            "type": "string"
        },
        "input_json": {
            "type": "string"
        },
        "stack": {
            "type": "string",
            "description": "stack to which tiles should be added"
        }
    }
}
```

output json:
```JSON
{
    "required": [
        "stack"
    ],
    "type": "object",
    "properties": {
        "stack": {
            "type": "string",
            "description": "stack to which generated tiles were added"
        }
    }
}
```
##  [generate_mipmaps.py](generate_mipmaps.py)
Create multiple mipmap levels based on an existing render stack.

input json:
```JSON
{
            "required": [
                "input_stack",
                "method",
                "output_dir"
            ],
            "type": "object",
            "properties": {
                "imgformat": {
                    "default": "tiff",
                    "type": "string",
                    "description": "image format for mipmaps (default tiff)"
                },
                "input_stack": {
                    "type": "string",
                    "description": "stack for which the mipmaps are to be generated"
                },
                "z": {
                    "type": "integer",
                    "description": "z-index in the stack",
                    "format": "int32"
                },
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
                "force_redo": {
                    "default": true,
                    "type": "boolean",
                    "description": "force re-generation of existing mipmaps"
                },
                "convert_to_8bit": {
                    "default": true,
                    "type": "boolean",
                    "description": "convert the data from 16 to 8 bit (default True)"
                },
                "zstart": {
                    "type": "integer",
                    "description": "start z-index in the stack",
                    "format": "int32"
                },
                "zend": {
                    "type": "integer",
                    "description": "end z-index in the stack",
                    "format": "int32"
                },
                "pool_size": {
                    "default": 20,
                    "type": "integer",
                    "description": "number of cores to be used",
                    "format": "int32"
                },
                "levels": {
                    "default": 6,
                    "type": "integer",
                    "description": "number of levels of mipmaps, default is 6",
                    "format": "int32"
                },
                "output_dir": {
                    "type": "string",
                    "description": "directory to which the mipmaps will be stored"
                },
                "output_json": {
                    "type": "string"
                },
                "input_json": {
                    "type": "string"
                },
                "method": {
                    "default": "block_reduce",
                    "type": "string",
                    "description": "method to downsample mipmapLevels, can be 'block_reduce' for skimage based area downsampling, 'PIL' for PIL Image (currently NEAREST) filtered resize, 'render' for render-ws based rendering.  Currently only PIL is implemented, while others may fall back to this."
                }
            }
        }

```

##  [apply_mipmaps_to_render.py](apply_mipmaps_to_render.py)
build render stack based on mipmaplevels in render's format (as generated by generate_mipmaps.py or render-ws clients)

```JSON

{
            "required": [
                "input_stack",
                "mipmap_dir"
            ],
            "type": "object",
            "properties": {
                "imgformat": {
                    "default": "tiff",
                    "type": "string",
                    "description": "mipmap image format, default is tiff"
                },        
                "close_stack": {
                    "default": false,
                    "type": "boolean",
                    "description": "whether to set output stack state to 'COMPLETE' upon completion"
                },
                "input_stack": {
                    "type": "string",
                    "description": "stack for which the mipmaps are to be generated"
                },
                "z": {
                    "type": "integer",
                    "description": "z-index of section in the stack",
                    "format": "int32"
                },
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
                "zstart": {
                    "type": "integer",
                    "description": "start z-index in the stack",
                    "format": "int32"
                },
                "zend": {
                    "type": "integer",
                    "description": "end z-index in the stack",
                    "format": "int32"
                },
                "output_stack": {
                    "default": null,
                    "x-nullable": true,
                    "type": "string",
                    "description": "the output stack name. Leave to overwrite input stack"
                },
                "pool_size": {
                    "default": 20,
                    "type": "integer",
                    "description": "number of cores to be used",
                    "format": "int32"
                },
                "levels": {
                    "default": 6,
                    "type": "integer",
                    "description": "number of levels of mipmaps, default is 6",
                    "format": "int32"
                },
                "mipmap_dir": {
                    "type": "string",
                    "description": "directory to which the mipmaps will be stored"
                },
                "output_json": {
                    "type": "string"
                },
                "input_json": {
                    "type": "string"
                }
            }
        }
```
