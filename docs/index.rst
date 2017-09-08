.. render-modules documentation master file, created by
   sphinx-quickstart on Thu Sep  7 12:25:36 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to render-modules's documentation!
==========================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Modules
---

Each render module's source code is listed below,
each module can be run as a script, and should default
to having exactly one ArgSchemaParser class in each module.

That class with specify the ArgSchema which should be contains its default
inputs.

If this is not the case, it is because the module is simply using ArgSchemaParser, 
without subclassing it and providing a new default schema.  In that case, you can simply 
examine the source code of the module, and the short __main__ function should call 
ArgSchemaParser with a schema_type, and you can find the schema_type documented in that 
modules documentation.

.. toctree::
   :maxdepth: 5

   rendermodules/modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
