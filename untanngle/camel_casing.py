def to_camel_case(text: str) -> str:
    s = text.replace("-", " ").replace("_", " ")
    s = s.split()
    if len(text) == 0:
        return text
    return s[0] + ''.join(i.capitalize() for i in s[1:])


def keys_to_camel_case(d: dict) -> dict:
    new_dict = {}
    for (k, v) in d.items():
        new_key = to_camel_case(k)
        if isinstance(v, dict):
            new_value = keys_to_camel_case(v)
        elif isinstance(v, list):
            new_value = _camel_case_list_elements(v)
        else:
            new_value = v
        new_dict[new_key] = new_value
    return new_dict


def _camel_case_list_elements(v):
    new_list = []
    for e in v:
        if isinstance(e, dict):
            new_element = keys_to_camel_case(e)
        elif isinstance(e, list):
            new_element = _camel_case_list_elements(e)
        else:
            new_element = e
        new_list.append(new_element)
    return new_list
