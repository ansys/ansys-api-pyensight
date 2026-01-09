import os
import re
from xml.etree import ElementTree

INDENT = "    "


class ProcessCalcuator:
    def __init__(self, data: str, math=False):
        self._root: ElementTree.Element = ElementTree.fromstring(data)
        self._processed = ""
        self._docstring = ""
        self._arg_types = {}
        self._prompts = {}
        self._end_lines = []
        self._math = math
    
    def process(self, dirname: str, filename: str):
        name = "ens_calculator"
        if self._math:
            name = "ens_math"
        output = f'"""{name} module"""\n'
        output+= f'"""The {name} module provides an interface to the EnSight {name.replace("ens_", "")} functions"""\n\n'
        output+= "try:\n"
        output+= f"{INDENT}import ensight\n"
        output+= "except ImportError:\n"
        output+= f"{INDENT}pass\n"
        output+= "from typing import TYPE_CHECKING, Union, List, Optional\n"
        output+= "from ansys.api.pyensight.ens_var import ENS_VAR\n"
        if not self._math:
            output += "from ansys.api.pyensight.calc_math import ens_math\n"
        output+= "from ansys.pyensight.core.utils.parts import convert_part\n"
        output+= "if TYPE_CHECKING:\n"
        output+= f"{INDENT}from ansys.api.pyensight import ensight_api\n\n"
        output+= f"{INDENT}from ansys.api.pyensight.ens_part import ENS_PART\n\n"
        output+= f"class {name}:\n"
        output+= f'{INDENT}def __init__(self, ensight: Union["ensight_api.ensight", "ensight"]):\n'
        output+= f"{2*INDENT}self._ensight = ensight\n"
        if not self._math:
            output+= f"{2*INDENT}self.math = ens_math(self._ensight)\n"
        output+= f"{2*INDENT}self._func_counter = {{}}\n\n"
        self._process_xml()
        output+= self._processed
        output+= "\n\n"
        for line in self._end_lines:
            output += line + "\n"
        with open(filename, "w") as f:
            f.write(output)

    def _register_prompts(self, prompts):
        for p in prompts:
            name = p.get("name")
            self._prompts[name] = p.text

    def _prompt_text(self, name):
        text = self._prompts.get(name, "Unknown")
        text = text.replace("Select a", "A").replace("Enter a", "A").replace("enter a", "a")
        text = text.replace("and select Next, ", "")
        text = text.replace("A Grad(|Velocity|) vector", "The gradient of the input velocity vector magnitude")
        return text

    def _register_types(self, types):
        for arg_type in types:
            name = arg_type.get("name")
            if "TURBO" in name:
                continue
            if "MASS_PTRACE" in name:
                continue
            self._arg_types[name] = set()
            current = self._arg_types[name]
            for arg in arg_type:
                if arg.tag == "builtin":
                    continue
                if arg.tag == "var_plist":
                    current.add("SOURCE_PARTS")
                    break
                if "part_" in arg.tag:
                    current.add("ENS_PART")
                if arg.tag in ["var_vector", "var_scalar", "var_const", "var_const_per_part", "var_scalar_complex", "var_vector_complex", "var_tensor"]:
                    current.add("ENS_VAR")
                if arg.tag in ["partid", "caseid"]:
                    current.add("int")
                if arg.tag == "val_enum":
                    current.add(f"enumvals='{arg[0].text}'")
                if arg.tag == "val_material":
                    current.add("ENS_MAT")
                if arg.tag == "val_species":
                    current.add("ENS_SPEC")
                if arg.tag == "val_float":
                    current.add("float")
                if arg.tag == "val_int":
                    current.add("int")
    
    def _process_args(self, args, prompts):
        is_list = False
        position = False
        prompts_dict = {name: prompt for name, prompt in prompts}
        # Pre-count total occurrences of each parameter name
        total_counts = {}
        for raw_param_name, _ in args:
            total_counts[raw_param_name] = total_counts.get(raw_param_name, 0) + 1
        # Track current occurrence index for each parameter name
        current_counts = {}
        for idx, (raw_param_name, param_type) in enumerate(args):
            param_name = raw_param_name
            # Track current occurrence (1-based)
            current_counts[raw_param_name] = current_counts.get(raw_param_name, 0) + 1
            done = False
            if ("(s)" in param_name):
                param_name = param_name.replace("(s)", "s")
                is_list = True
            _type = self._arg_types.get(param_type)
            if not _type:
                continue
            name = param_name.replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "").replace(".", "").replace("+", "_").replace("[", "").replace("]", "")
            if str(name[0]).isdigit():
                name = "choose_" + name
            # Append suffix for duplicate parameter names (only if there are multiple)
            if total_counts[raw_param_name] > 1:
                name = f"{name}_{current_counts[raw_param_name]}"
            doc_name = name
            if len(_type) == 1:
                last = ""
                if list(_type)[0] == "SOURCE_PARTS":
                    self._processed+= "source_parts: Union[List['ENS_PART'], List[int], List[str], 'ENS_PART', int, str], "
                    last = "Union"
                    done = True
                    doc_name = "source_parts"
                    self._docstring += f"\n{2*INDENT}Args:\n"
                if list(_type)[0] == "ENS_PART":
                    if is_list:
                        self._processed+= f"{name}: List['ENS_PART'], "
                        last = "List"
                    else:
                        self._processed+= f"{name}: 'ENS_PART', "
                        last = "'ENS_PART'"
                    done = True
                if list(_type)[0] == "ENS_VAR":
                    self._processed+= f"{name}: Union['ENS_VAR', str, int], "
                    last = "Union"
                    done = True
                if list(_type)[0] == 'int':
                    self._processed+= f"{name}: int, "
                    last = "int"
                    done = True
                if list(_type)[0] == 'float':
                    self._processed+= f"{name}: float, "
                    last = "float"
                    done = True
                if list(_type)[0] == 'ENS_MAT':
                    last = "ENS_MAT"
                    self._processed+= f"{name}: 'ENS_MAT', "
                    done = True
                if list(_type)[0] == 'ENS_SPEC':
                    last = "ENS_SPEC"
                    self._processed+= f"{name}: 'ENS_SPEC', "
                    done = True
                if position and done:
                    self._processed = self._processed[:-2] + "] = None, " 
                    index = self._processed.rfind(last)
                    self._processed = self._processed[:index] + "Optional[" + self._processed[index:]
                if "enumvals" in list(_type)[0]:
                    position = True
                    def_value = list(_type)[0].replace("enumvals=", "")
                    type_hint = "str"
                    try:
                        def_value = int(def_value.replace("'", ""))
                        type_hint = "int"
                    except:
                        pass
                    self._processed += (f"{name}: {type_hint} = {def_value}, ")
            else:
                has_source_parts = any(["SOURCE_PARTS" == sub_type for sub_type in _type])
                if has_source_parts:
                    self._processed += f"{name}: List['ENS_PART', "
                    done = True
                else:
                    self._processed += f"{name}: Union["
                    for sub_type in _type:
                        if sub_type == "ENS_VAR":
                            self._processed += "'ENS_VAR', str, int" +", "
                        else:
                            self._processed += f"'{sub_type}'" +", "
                    done = True
                self._processed = self._processed[:-2] + "], "
                if position and done:
                    self._processed = self._processed[:-2] + "] = None, "
                    index = self._processed.rfind("Union")
                    self._processed = self._processed[:index] + "Optional[" + self._processed[index:]
                done = True
            self._docstring += f"{3*INDENT}{doc_name}:\n"
            self._docstring += f"{4*INDENT}{self._prompt_text(prompts_dict.get(raw_param_name, ''))}\n"
        self._processed += "output_varname: Optional[str] = None)"
        self._docstring += f"{3*INDENT}output_varname:\n"
        self._docstring += f"{4*INDENT}The name of the newly created variable\n"

    def _find_var_args(self, args):
        var_args = []
        # Pre-count total occurrences of each parameter name
        total_counts = {}
        for param_name, _ in args:
            total_counts[param_name] = total_counts.get(param_name, 0) + 1
        # Track current occurrence index for each parameter name
        current_counts = {}
        for param_name, param_type in args:
            _type = self._arg_types.get(param_type)
            if not _type:
                continue
            # Track current occurrence (1-based)
            current_counts[param_name] = current_counts.get(param_name, 0) + 1
            name = param_name.replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "").replace(".", "").replace("+", "_").replace("[", "").replace("]", "")
            if str(name[0]).isdigit():
                name = "choose_" + name
            # Append suffix for duplicate parameter names (only if there are multiple)
            if total_counts[param_name] > 1:
                name = f"{name}_{current_counts[param_name]}"
            if len(_type) == 1:
                if list(_type)[0] == "ENS_VAR":
                    var_args.append(name)
            else:
                if any([subtype == "ENS_VAR" for subtype in _type]):
                    var_args.append(name)
        return var_args
                    
    def _process_return_type(self, return_type):
        self._processed += f" -> '{list(self._arg_types[return_type])[0]}':"
                   
    def _register_functions(self, functions):
        for func in functions:
            name = func.get("name")
            if not any([x.tag == "visible" for x in func]):
                continue
            visible = [x for x in func if x.tag == "visible"][0]
            if visible.text:
                continue
            args = []
            prompts = []
            result_type = None
            desc = None
            metadata  = {"class": [], "vartype": [], "name": func.get("name"), "dimensions": None}
            for attr in func:
                if attr.tag == "description":
                    desc = attr.text
                if attr.tag == "param":
                    args.append((attr.get("name"), [x.get("name") for x in attr if x.tag == "type"][0]))
                    if name == "IF_LT":
                        prompt = "MATH_VARFLT"
                    else:
                        prompt = [x.get("name") for x in attr if x.tag == "prompt"][0]
                    prompts.append((attr.get("name"), prompt))
                if attr.tag == "result":
                    result_type = [x.get("name") for x in attr if x.tag == "type"][0]
                    dimensions = [x.text for x in attr if x.tag == "dimensions"][0]
                    metadata["dimensions"] = dimensions
                if attr.tag == "vartype":
                    for vart in attr:
                        if vart.tag != "arg":
                            metadata["vartype"].append(vart.tag)
                if attr.tag == "class":
                    metadata["class"].append(attr.text)
            class_name = "ens_calculator"
            if self._math:
                class_name = "ens_math"
            self._end_lines.append(f"{class_name}.{name.lower()}.meta = {metadata}")
            self._processed += f"{INDENT}def {name.lower()}(self, "
            self._docstring = f'\n{2*INDENT}"""'
            if desc:
                self._docstring += desc
            self._docstring += "\n"
            self._process_args(args, prompts)
            var_args = self._find_var_args(args)
            if result_type:
                self._process_return_type(result_type)
            self._processed += self._docstring
            self._processed += f"\n{2*INDENT}Returns:\n"
            self._processed += f"{3*INDENT}New ENS_VAR instance or None\n"
            self._processed += f"\n{2*INDENT}Note:\n"
            self._processed += f'{3*INDENT}See :any:`{name}` for function details.\n{2*INDENT}"""'
            self._processed += f'\n{2*INDENT}params_dict = {{x:y for x,y in locals().items() if x != "self" and x != "output_varname"}}'
            self._processed += f'\n{2*INDENT}sources = None'
            self._processed += f'\n{2*INDENT}if params_dict.get("source_parts"):'
            self._processed += f'\n{3*INDENT}params_dict["source_parts"] = "plist"'
            self._processed += f'\n{3*INDENT}part_numbers = [convert_part(self._ensight, p) for p in source_parts]'
            self._processed += f'\n{3*INDENT}sources = self._ensight.objs.core.PARTS.find(part_numbers,attr="PARTNUMBER")'
            self._processed += f'\n{2*INDENT}for var_arg in {var_args}:'
            self._processed += f'\n{3*INDENT}if isinstance(params_dict.get(var_arg), int):'
            self._processed += f'\n{4*INDENT}if params_dict.get(var_arg) >= 0:'
            self._processed += f'\n{5*INDENT}params_dict[var_arg] = self._ensight.objs.core.VARIABLES.find([params_dict.get(var_arg)], attr="ID")[0].DESCRIPTION'
            self._processed += f"\n{2*INDENT}for param_name, param_val in params_dict.items():"
            self._processed += f"\n{3*INDENT}if isinstance(param_val, ENS_VAR):"
            self._processed += f"\n{4*INDENT}params_dict[param_name] = param_val.DESCRIPTION"
            self._processed += f"\n{3*INDENT}if param_val is None:"
            self._processed += f"\n{4*INDENT}params_dict[param_name] = -1"
            self._processed += f"\n{2*INDENT}if not output_varname:"
            self._processed += f'\n{3*INDENT}if not self._func_counter.get("{name}"):'
            self._processed += f'\n{4*INDENT}self._func_counter["{name}"] = 0'
            self._processed += f'\n{3*INDENT}else:'
            self._processed += f'\n{4*INDENT}self._func_counter["{name}"] += 1'
            self._processed += f'\n{3*INDENT}counter = self._func_counter["{name}"]'
            self._processed += f'\n{3*INDENT}output_varname = f"{name}_{{counter}}"'
            self._processed += f'\n{2*INDENT}if len(params_dict.values()) > 0:'
            self._processed += f"""\n{3*INDENT}val = repr(list(params_dict.values()))[1:-1].replace("'", "")"""
            self._processed += f"\n{3*INDENT}return self._ensight.objs.core.create_variable(f'{{output_varname}}', f'{name}({{val}})', sources=sources)"
            self._processed += f"\n{2*INDENT}return self._ensight.variables.evaluate(f'{{output_varname}}={name}()')\n\n"

    def _process_xml(self):
        for node in self._root:
            if node.tag == "prompts":
                self._register_prompts(node)
            if node.tag == "types":
                self._register_types(node)
            if node.tag == "server" or node.tag == "math":
                self._register_functions(node)
        
        