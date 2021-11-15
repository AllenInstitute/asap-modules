# module

This is a submodule that contains the generic module subcomponents that extend ArgSchemaParser to do the common patterns that are used throughput many of the modules.

### render_module
A set of extensions of argschema classes specific to workflows that involve render.  Defines RenderParameters, a schema which has a nested render schema for connecting to a specific render host,port,project,owner and client_scripts locations via the renderapi.  A corresponding RenderModule for processing parameters and initializing a render object at self.render. Some other common patterns in this module as well, such as interacting with TrakEM2 and moving data between multiple render servers.

### template_module
This is the basic template pattern for creating a new module. 

