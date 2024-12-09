import os
import re
from xml.etree import ElementTree
from typing import Optional, Any, TYPE_CHECKING

INDENT = "    "

if TYPE_CHECKING:
    from stub_api import XMLOverrides

class ProcessDVS:
    def __init__(self, data: str, overrides):
        self._root: ElementTree.Element = ElementTree.fromstring(data)[0]
        self._overrides: "XMLOverrides" = overrides
        self._processed = ""
        self._docstring = ""
        self._arg_types = {}
        self._prompts = {}
    
    def process(self, dirname: str, filename: str):
        output = '"""dvs_base module"""\n'
        output+= '"""Thed dvs_base module provides an interface to the dynamic_visualization store module"""\n\n'
        output+= "from typing import Any, Optional, List, Dict, Tuple, TYPE_CHECKING\n\n"
        output+= "import numpy\n"
        output+= "numpy.set_printoptions(threshold=numpy.inf)\n"
        output+= "numpy.set_printoptions(linewidth=numpy.inf)\n\n"
        output+= "if TYPE_CHECKING:\n"
        output+= "    from ansys.pyensight.core import Session\n"
        output+= "class dvs_base:\n"
        output+= f'{INDENT}def __init__(self, session: Optional["Session"]=None, dvs_module: Optional[Any]=None):\n'
        output += f'{2*INDENT}self._session = session\n'
        output += f'{2*INDENT}self._dvs_module = dvs_module\n'
        self._process_xml()
        output+= self._processed
        with open(filename, "w") as f:
            f.write(output)

    def _replace(
        self,
        namespace: str,
        attribute: str = "description",
        default: Optional[str] = None,
        indent: str = "",
        simple: bool = False,
    ) -> Any:
        """Allow replacement of a given attribute for a given namespace
        When looking up an attribute for a given node namespace, allow for
        external replacement of a specific attribute.  Note: this is presently
        only used for 'description' attributes.

        Args:
            namespace:
                The namespace for the query
            attribute:
                The name of the attribute to be considered
            default:
                The default value to be returned if no replacement is to be made
            indent:
                This prefix should be used for all lines after the first line.
            simple:
                If True, no post-processing will be performed.
        Returns:
            The attribute replacement
        """
        if self._overrides is None:
            return default
        value = self._overrides.replace(namespace, attribute, default)
        if type(value) == str:
            if simple:
                return value.strip().replace("\r", "").replace("\n", "")
            lines = value.strip().replace("\r", "").split("\n")
            tmp_indent = ""
            value = ""
            for line in lines:
                value += tmp_indent
                value += line + "\n"
                tmp_indent = indent
        return value

    @staticmethod
    def _cap1(s: Optional[str]) -> Optional[str]:
        if s:
            return s[0].upper() + s[1:]
        return s

    def _process_undefined_callable(
        self,
        node: ElementTree.Element,
        indent: str = "",
    ) -> str:
        """Generate bindings for a callable w/o explicit parameter description

        The callable can be an object method or a general function (which is mapped to an
        object method in the pyensight scheme for mapping modules into classes).

        Args:
            node:
                The node in the XML API description
            indent:
                The current output text indent string
            classname:
                If a specific class, the name of the class
        Returns:
            The generated Python binding source code or an empty string (on failure).
        """
        name = node.get("name")
        new_indent = indent + "    "
        # get the namespace for the function
        namespace = node.get("ns")
        # get the description, potentially with substitution
        desc = node.get("description", "")
        desc = self._replace(namespace, default=desc, indent=new_indent)
        # signature is '(param:type, param2:type, ...) -> type'
        # paramnames is '[param, param2 ...]' if a param name ends with '=' it is a keyword
        signature = "(*args, **kwargs) -> Any"
        paramnames = self._replace(namespace, "paramnames", None, simple=True)
        if paramnames is not None:
            signature = self._replace(namespace, "signature", signature, simple=True)
            paramnames = eval(paramnames)
        if "empty" in signature:
            signature = "(self) " + signature[signature.index("-"):]
        else:
            signature = "(self, " + signature[1:]
        
        if "List[Any] = None" in signature:
            signature = signature.replace("List[Any]", "Optional[List[Any]]")
        if "List[int] = None" in signature:
            signature = signature.replace("List[int]", "Optional[List[int]]")
        if "-> list" in signature:
            signature = signature.replace("-> list", "-> List[Any]")
        code = self._replace(namespace, "code", default=None, indent=new_indent)
        # Start recording
        s = "\n"
        s += f"{indent}def {name}{signature}:\n"
        if desc:
            desc = self._cap1(desc)
            s += f'{new_indent}"""{desc}\n'
            s += f'{new_indent}"""\n'
        if code:
            s += new_indent + code
            return s  # TODO: for the moment, code replacement blocks are not auto-tested
        else:
            module_signature = "*args, **kwargs"
            if paramnames:
                if "empty" in paramnames:
                    module_signature = ""
                else:
                    module_signature = ", ".join(paramnames)
                    module_signature = module_signature.replace("=", "")
            s += f"{new_indent}if self._dvs_module:\n"
            s += f"{new_indent}    return self._dvs_module.{name}({module_signature})\n"
            s += f"{new_indent}if self._session:\n"
            s += f"{new_indent}    self._session.cmd('import dynamic_visualization_store', do_eval=False)\n"
            s += f"{new_indent}    self._session.cmd('import numpy', do_eval=False)\n"
            s += f"{new_indent}    arg_list = []\n"
            if paramnames is not None:
                if not "empty" in paramnames:
                    for p in [s for s in paramnames if not s.endswith("=")]:
                        s += f"{new_indent}    data = {p}.__repr__()\n"
                        s += f"{new_indent}    if isinstance({p}, numpy.ndarray):\n"
                        s += f'{new_indent}        data = data.replace("array(", "numpy.array(").replace("float32", "numpy.float32")\n'
                        s += f"{new_indent}    arg_list.append(data)\n"
            else:
                s += f"{new_indent}    for arg in args:\n"
                s += f"{new_indent}        arg_list.append(arg.__repr__())\n"
                # keywords
            if paramnames is not None:
                if not "empty" in paramnames:
                    for p in [s for s in paramnames if s.endswith("=")]:
                        s += f'{new_indent}    data = {p[:-1]}.__repr__()\n'
                        s += f'{new_indent}    if isinstance({p[:-1]}, numpy.ndarray):\n'
                        s += f'{new_indent}        data = data.replace("array(", "numpy.array(").replace("float32", "numpy.float32")\n'
                        s += f'{new_indent}    arg_list.append(data)\n'
            else:
                s += f"{new_indent}    for key, value in kwargs.items():\n"
                s += f'{new_indent}        data = value.__repr__()\n'
                s += f'{new_indent}        if isinstance(value, numpy.ndarray):\n'
                s += f'{new_indent}            data = data.replace("array(", "numpy.array(").replace("float32", "numpy.float32")\n'
                s += f'{new_indent}        arg_list.append(data)\n'
                # build the command
            s += f'{new_indent}    arg_string = ",".join(arg_list)\n'
            s += f'{new_indent}    cmd = f"{namespace}({{arg_string}})"\n'
            s += f"{new_indent}    return self._session.cmd(cmd)\n"
        return s

    @staticmethod
    def _process_variable(node: ElementTree.Element, indent: str = "") -> str:
        """Process <variable> tag

        Variable tags are converted into class members
        """
        var_type = node.get("type", "Any")
        s = f"{indent}self.{node.get('name')}: {var_type}"
        if node.text:
            if var_type == "str":
                s += f" = '{node.text}'"
            else:
                s += f" = {node.text}"
        return s + "\n"

    def _process_module(self, node: ElementTree.Element, indent: str = "") -> str:
        """Process a <module> tag

        Module tags are converted into classes
        """
        s = "\n\n"
        s += f"{indent}class {node.get('name')}:\n"
        indent += "    "
        desc = node.get("description", f"class wrapper for DVS {node.get('name')} module")
        desc = self._replace(node.get("ns"), default=desc, indent=indent)
        desc = self._cap1(desc)
        s += f'{indent}"""{desc}\n'
        s += f"{indent}This class acts as a proxy for the DVS Python module {node.get('ns')}\n"
        s += "__ATTRIBUTES__"
        s += f'{indent}"""\n'
        init = f"{indent}def __init__(self):\n"
        s += init

        attributes = ""
        # walk the children
        methods = ""
        at_least_one_variable = False
        at_least_one_module = False
        for child in node:
            if child.tag == "variable":
                at_least_one_variable = True
                s += self._process_variable(child, indent=f"{indent}    ")
                prop_type = child.get("type", "Any")
                attributes += f"{indent}    {child.get('name')} ({prop_type}):\n"
                attributes += f"{indent}        Instance specific constant\n\n"
            elif child.tag == "module":
                # Prepend the submodule
                at_least_one_module = True
                name = child.get("name")
                s = self._process_module(child) + s
                # add an instance of the class to the current class
                s += f"{indent}    self.{name}: '{name}' = {name}()\n"
                attributes += f"{indent}    {name}:\n"
                attributes += f"{indent}        EnSight module instance class\n\n"
            elif child.tag == "method":
                methods += self._process_undefined_callable(
                    child, indent=indent
                )
        
        if not at_least_one_variable and not at_least_one_module:
            s = s.replace(init, f"{init}{indent}    pass\n")

        s += methods
        if attributes:
            attributes = f"\n{indent}Attributes:\n" + attributes + "\n"

        if s.endswith(init):
            s = s.replace(init, "")

        return s.replace("__ATTRIBUTES__", attributes)


    def _process_xml(self):
        variables = [n for n in self._root if n.tag == "variable"]
        for v in variables:
            self._processed += self._process_variable(v, indent=2*INDENT)
        for node in self._root:
            if node.tag == "module":
                self._processed += self._process_module(node, indent=INDENT)
            if node.tag == "method":
                self._processed += self._process_undefined_callable(node, indent=INDENT)

        
        