import os
import re
from xml.etree import ElementTree

INDENT = "    "


class ProcessCalcuator:
    def __init__(self, data: str):
        self._root: ElementTree.Element = ElementTree.fromstring(data)
        self._processed = ""
        self._arg_types = {}
    
    def process(self, dirname: str, filename: str):
        output = '"""ens_calculator module"""\n'
        output+= '"""The ens_calculator module provides an interface to the EnSight calculator functions"""\n\n'
        output+= "from typing import TYPE_CHECKING, Union, List\n"
        output+= "from ansys.api.pyensight.ens_var import ENS_VAR\n"
        output+= "from ansys.pyensight.core.utils.parts import convert_part\n"
        output+= "if TYPE_CHECKING:\n"
        output+= f"{INDENT}from ansys.pyensight.core.session import Session\n"
        output+= f"{INDENT}from ansys.api.pyensight.ens_part import ENS_PART\n\n"
        output+= "class ens_calculator:\n"
        output+= f"{INDENT}def __init__(self, session: 'Session'):\n"
        output+= f"{2*INDENT}self._session = session\n\n"
        self._process_xml()
        output+= self._processed
        with open(filename, "w") as f:
            f.write(output)
        
    def _register_prompts(self, types):
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
    
    def _process_args(self, args):
        is_list = False
        arg_counter = 0
        part_counter = 0
        var_counter = 0
        position = False
        for param_name, param_type in args.items():
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
            if len(_type) == 1:
                if list(_type)[0] == "SOURCE_PARTS":
                    self._processed+= "source_parts: Union[List['ENS_PART'], List[int], List[str]], "
                    done = True
                if list(_type)[0] == "ENS_PART":
                    if is_list:
                        self._processed+= f"{name}: List['ENS_PART'], "
                    else:
                        self._processed+= f"{name}: 'ENS_PART', "
                    done = True
                    part_counter += 1
                if list(_type)[0] == "ENS_VAR":
                    self._processed+= f"{name}: Union['ENS_VAR', str], "
                    var_counter += 1
                    done = True
                if list(_type)[0] == 'int':
                    self._processed+= f"{name}: int, "
                    arg_counter +=1
                    done = True
                if list(_type)[0] == 'float':
                    self._processed+= f"{name}: float, "
                    arg_counter +=1
                    done = True
                if list(_type)[0] == 'ENS_MAT':
                    self._processed+= f"{name}: 'ENS_MAT', "
                    done = True
                if list(_type)[0] == 'ENS_SPEC':
                    self._processed+= f"{name}: 'ENS_SPEC', "
                    done = True
                if position and done:
                    self._processed = self._processed[:-2] + "=-1, " 
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
                    arg_counter += 1
            else:
                has_source_parts = any(["SOURCE_PARTS" == sub_type for sub_type in _type])
                if has_source_parts:
                    self._processed += f"{name}: List['ENS_PART', "
                    done = True
                else:
                    self._processed += f"{name}: Union["
                    for sub_type in _type:
                        if sub_type == "ENS_VAR":
                            self._processed += "Union['ENS_VAR', str]" +", "
                        else:
                            self._processed += f"'{sub_type}'" +", "
                    done = True
                self._processed = self._processed[:-2] + "], "
                if position and done:
                    self._processed = self._processed[:-2] + "=-1, " 
                done = True
                arg_counter += 1
        self._processed = self._processed[:-2]
        self._processed += ")"
                    
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
            args = {}
            result_type = None
            desc = None
            for attr in func:
                if attr.tag == "description":
                    desc = attr.text
                if attr.tag == "param":
                    args[attr.get("name")] = [x.get("name") for x in attr if x.tag == "type"][0]
                if attr.tag == "result":
                    result_type = [x.get("name") for x in attr if x.tag == "type"][0]
            self._processed += f"{INDENT}def {name.lower()}(self, "
            self._process_args(args)
            if result_type:
                self._process_return_type(result_type)
            if desc:
                self._processed += f'\n{2*INDENT}"""{desc}\n'
                self._processed += f'\n{2*INDENT}See :any:`{name}` for the details."""\n'
            self._processed += f'\n{2*INDENT}params = [y for x,y in locals().items() if x != "self" and x != "source_parts"]'
            self._processed += f'\n{2*INDENT}has_source_parts = any([x=="source_parts" for x,y in locals().items()])'
            self._processed += f'\n{2*INDENT}sources = None'
            self._processed += f'\n{2*INDENT}if has_source_parts:'
            self._processed += f'\n{3*INDENT}params.insert(0, "plist")'
            self._processed += f'\n{3*INDENT}part_numbers = [convert_part(self._session.ensight, p) for p in source_parts]'
            self._processed += f'\n{3*INDENT}sources = self._session.ensight.objs.core.PARTS.find(part_numbers,attr="PARTNUMBER")'
            self._processed += f"\n{2*INDENT}for idx, param in enumerate(params):"
            self._processed += f"\n{3*INDENT}if isinstance(param, ENS_VAR):"
            self._processed += f"\n{4*INDENT}params[idx] = param.DESCRIPTION"
            self._processed += f'\n{2*INDENT}if len(params) > 0:'
            self._processed += f"""\n{3*INDENT}val = repr(params)[1:-1].replace("'", "")"""
            self._processed += f"\n{3*INDENT}return self._session.ensight.objs.core.create_variable('{name}', f'{name}({{val}})', sources=sources)"
            self._processed += f"\n{2*INDENT}return self._session.ensight.variables.evaluate(f'{name}={name}()')\n\n"
            
            
            
                
    
    def _process_xml(self):
        for node in self._root:
            if node.tag == "prompts":
                continue
            if node.tag == "types":
                self._register_prompts(node)
            if node.tag == "server":
                self._register_functions(node)
        
        