## What does this repo do?

The pyensight project uses an API that is scraped nightly from
EnSight builds.  The files in src/ansys/api/pyensight/v0 are
collected from EnSight builds.  The protobuffer interfaces
are included and the 'ensight_api.xml' file.  The latter
contains a fairly complete description of the EnSight Python
APIs (native and object).  

The stub_api.py script is used 
by setup.py to generate Python source code files in the
src/ansys/api/pyensight directory.  Those files are used
by the ansys-pyensight-core project as the interface to
EnSight. Building this repo generates an ansys-api-pyensight 
wheel that the pyensight project depends on.

## How does it work?

When the EnSight API changes, a new 'ensight_api.xml' file
is merged into this repo by hand, the version of the repo is
bumped and committed.  The pyensight repo dependency is then
updated to the new version.

### Auto-generation of the interface files

Most of this is handled by the stub_api.py script which 
simply walks the input XML, generating python source code
files along the way.  It is a fairly automated process that
generates "functional" bindings, that in many cases lack
detailed documentation.

### Customized docstrings/etc

There is a mechanism that allows a developer to override
the auto-generated bindings.  This can be used to improve
the documentation for methods, provide more explicit 
interfaces and even custom binding implementations.

In the doc/replacements directory, there are a collection of
XML files.  The stub_api.py script reads all the XML files
in replacements and subdirectories looking in the \<docstrings\>
tag for \<override\> tags.  These are parsed and used to 
inform the generation of Python bindings.

### \<docstrings>

The XML file itself should have one and only one of these.
It can only contain \<override\> tags.

### \<override namespace="name">

This tag defines an API target for customization.  An example might be:

    <override namespace=”ensight.objs.ENS_VPORT.transform”>

The tags within this one would apply to the generation of the bindings for
the ensight.objs.ENS_VPORT.transform() method.

### \<signature>

This tag replaces the method signature entirely with custom code.  For example:

    <override namespace="ensight.idle">
    <signature>(yield_cpu: bool = False) -> None</signature>
    </override>

Specifies that the binding for the method will look like this:

    def idle(yield_cpu: bool = False) -> None:

vs a more generic "arg1" with no type hint.

> Note: this is actual Python code and not just documentation, but it is a
> good place to include more complete Python type hints.

### \<paramnames> 

Is used to specify the name and type of each argument in the signature.
For example:

    <paramnames>["yield_cpu="]</paramnames>

Specifies that there is one, argument, named "yield_cpu" and that it is a keyword argument.
The "=" is only included for keyword arguments.  Required, positional arguments need to
be specified before any keyword arguments and should not have the trailing "=".

### \<description>

This tag specifies the actual docstrings text, verbatim, examples and all.  It should 
follow the rules of whatever format processing pipeline is being used.  An example 
might be:

    <description>
    Execute EnSight idle processing

    Call the EnSight idle processing loop a single time.  It is used in closed
    Python loops where EnSight idle processing (animation, gRPC, etc) needs to
    be allowed to take place.
     
    Args:
        yield_cpu:
            If True, the call will give up the cpu time slice when executing
            the idle loop.  It can help reduce cpu utilization while polling.
    </description>

> Note: the text should not be indented as the python script will perform that operation.  
> Remember that this is an XML files and XML escaping rules need to be followed for
> various characters.

### \<code>

This tag allows for the XML file to specify custom Python code that implements
the bindings.  See ensight.objs.ENS_PART.get_values for an example of how this
is done.
