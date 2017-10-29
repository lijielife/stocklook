# -*- coding: utf-8 -*-
"""
Created on Wed Nov  2 14:55:15 2016

@author: zbarge
"""

from pandas import Timestamp
import xml.etree.cElementTree as ET



STRINGS_TO_DTYPE = {'str': str,
                    'Timestamp': Timestamp,
                    'DateTime': Timestamp,
                    'datetime': Timestamp,
                    'float': float,
                    'int': int,
                    'bool': bool
                    }
STRINGS_TO_DTYPE.update({v: v for v in STRINGS_TO_DTYPE.values()})

NULLS = ['NA', None, 'None', 'null']

STRINGS_TO_FALSE = ['no', 'false', 'null', '', 'none', 'na', 'nan', 'nat', '0']


def format_dollar_letter_conversions(value):
    try:
        value = str(value)
        bit = value[-1].upper()

        if not bit.isdigit():
            value = value.replace(bit, '').lstrip().rstrip()

            if bit == 'M':
                value = float(value) * 1000000
            elif bit == 'B':
                value = float(value) * 1000000000

        return float(value)
    except ValueError:
        return float(0)


def raw_string(x):
    try:
        return r"{}".format(x.__name__)
    except:
        return r"{}".format(x)


def ensure_float(x):
    x = format_dollar_letter_conversions(str(x).replace('%', '').lstrip().rstrip())
    try:
        return float(x)
    except:
        return float(0)


def ensure_int(x):
    x = format_dollar_letter_conversions(str(x)
                                         .replace('%', '')
                                         .replace('$', '')
                                         .lstrip()
                                         .rstrip())
    try:
        return int(x)
    except:
        return 0


def ensure_string(x):
    try:
        return str(x)
    except:
        return ''


def ensure_bool(x):
    x = str(x).lower().lstrip().rstrip()
    if x in STRINGS_TO_FALSE:
        return False
    return True


def ensure_datetime(x):
    try:
        t = Timestamp(x)
        if 'NaT' in str(t):
            return Timestamp('1900-01-01')
        return t
    except:
        return Timestamp('1900-01-01')


DTYPE_CONVERTERS = {str: ensure_string,
                    float: ensure_float,
                    int: ensure_int,
                    bool: ensure_bool,
                    Timestamp: ensure_datetime}


NAME = 'NAME'
RENAME = 'RENAME'
DTYPE = 'DTYPE'
FIELDS = 'FIELDS'
INCLUDE = 'INCLUDE'


def generate_config(module, renames, dtypes):
    """
    Returns a dictionary of
    {module:{FIELDS:{field:{RENAME:renames[field], DTYPE:dtypes[field], INCLUDE:True/False}
                                }}}
    module: (str) - name of module

    """
    fields = {}
    for field, newfield in renames.items():
        dtype = dtypes.get(field, None)
        if dtype is None or newfield in NULLS:
            include = False
            dtype = str
        else:
            include = True
        data = {field: {RENAME: newfield, DTYPE: raw_string(dtype), INCLUDE: include}}
        fields.update(data)
    return {module: {FIELDS: fields}}


def parse_config(config):
    """
    Parses a Zoho field configuration map.
    Checks for presence of required keys to make
    the program work and raises an error if any.
    converts string dtypes to python dtypes.
    """
    config = config.copy()
    for module, data in config.items():
        fields = data.get(FIELDS, None)
        assert fields is not None, "Expected a {} dictionary, got None".format(FIELDS)
        for field, info in fields.items():
            try:
                rename = info[RENAME]
                dtype = info[DTYPE]
                include = info[INCLUDE]
            except KeyError as e:
                raise KeyError("Field '{}' missing required key '{}'. "
                               "module is {}".format(field, e, module))

            try:
                config[module][FIELDS][field][DTYPE] = STRINGS_TO_DTYPE[dtype]
            except KeyError:
                if dtype in NULLS:
                    config[module][FIELDS][field][DTYPE] = str
                else:
                    raise KeyError("Field '{}' has an invalid dtype: '{}'. module is {}".format(field, dtype, module))
    return config


class DictParser:
    def __init__(self):
        pass

    @staticmethod
    def parse_dtypes(record_dict, dtype_map, default=str, raise_on_error=True):
        """
        parses the dtypes of the values in record_dict
        using the functions defined in the field_dtypes_dict
        record_dict            A dictionary of {field_name:value}
        dtype_map              A dictionary of {field_name:dtype}
        default                The datatype to default to.
        raise_on_error         True raises KeyErrors, False defaults to default dtype.
        """
        new = {}
        for field, value in record_dict.items():
            try:
                dtype = dtype_map[field]
            except KeyError:
                if raise_on_error:
                    raise
                dtype = str

            try:
                new[field] = DTYPE_CONVERTERS[dtype](value)
            except KeyError:
                if raise_on_error:
                    raise NotImplementedError("dtype '{}' is unsupported".format(dtype))
                new[field] = default(value)

        return new

    @staticmethod
    def rename_dict(dict_to_rename, dict_map):
        new = {}
        for field, value in dict_to_rename.items():
            try:
                field = dict_map[field]
            except KeyError:
                pass
            new[field] = value
        return new

    @staticmethod
    def get_merged_dict(*dicts):
        merged_dict = {}
        [merged_dict.update(d) for d in dicts]
        return merged_dict

    @staticmethod
    def get_dict_keys(dict_to_filter, include_list):
        return {field: value for field, value in dict_to_filter.items() if field in include_list}

    @staticmethod
    def drop_dict_keys(dict_to_filter, exclude_list):
        return {field: value for field, value in dict_to_filter.items() if not field in exclude_list}

    @staticmethod
    def drop_dict_values(dict_to_filter, exclude_list):
        return {field: value for field, value in dict_to_filter.items() if not value in exclude_list}


class XmlList(list):
    def __init__(self, aList):
        for element in aList:
            if element:
                # treat like dict
                if len(element) == 1 or element[0].tag != element[1].tag:
                    self.append(XmlDict(element))
                # treat like list
                elif element[0].tag == element[1].tag:
                    self.append(XmlList(element))
            elif element.text:
                text = element.text.strip()
                if text:
                    self.append(text)


class XmlDict(dict):
    '''
    Example usage:

    >>> tree = ElementTree.parse('your_file.xml')
    >>> root = tree.getroot()
    >>> xmldict = XmlDictConfig(root)

    Or, if you want to use an XML string:

    >>> root = ElementTree.XML(xml_string)
    >>> xmldict = XmlDictConfig(root)

    And then use xmldict for what it is... a dict.
    '''

    def __init__(self, parent_element):
        if isinstance(parent_element, (str, bytes)):
            parent_element = ET.XML(parent_element)
        if parent_element.items():
            self.update(dict(parent_element.items()))
        for element in parent_element:
            if element:
                # treat like dict - we assume that if the first two tags
                # in a series are different, then they are all different.
                if len(element) == 1 or element[0].tag != element[1].tag:
                    aDict = XmlDict(element)
                # treat like list - we assume that if the first two tags
                # in a series are the same, then the rest are the same.
                else:
                    # here, we put the list in dictionary; the key is the
                    # tag name the list elements all share in common, and
                    # the value is the list itself
                    aDict = {element[0].tag: XmlList(element)}
                # if the tag has attributes, add those to the dict
                if element.items():
                    aDict.update(dict(element.items()))
                self.update({element.tag: aDict})
            # this assumes that if you've got an attribute in a tag,
            # you won't be having any text. This may or may not be a
            # good idea -- time will tell. It works for the way we are
            # currently doing XML configuration files...
            elif element.items():
                self.update({element.tag: dict(element.items())})
            # finally, if there are no child tags and no attributes, extract
            # the text
            else:
                self.update({element.tag: element.text})


def test_XmlDict():
    string = b'<?xml version="1.0" encoding="UTF-8" ?>\n<response uri="/crm/private/xml/CustomModule4/insertRecords">' \
             b'<result><message>Record(s) added successfully</message><recorddetail><FL val="Id">1706004000002464015</FL>' \
             b'<FL val="Created Time">2016-09-26 16:15:32</FL><FL val="Modified Time">2016-09-26 16:15:32</FL><FL val="Created By">' \
             b'<![CDATA[Data]]></FL><FL val="Modified By"><![CDATA[Data]]></FL></recorddetail></result></response>\n'
    xd = XmlDict(string)
    assert isinstance(xd, dict), "Expected to get a dictionary, not {}".format(type(xd))
    assert xd.get('uri', None) == '/crm/private/xml/CustomModule4/insertRecords'
    details = xd['result']['recorddetail']
    assert isinstance(details, dict), "Expected to get a dictionary, not {}".format(type(details))
    print('tests passed OK')


def sanatize_field(field):
    for char in ['-', ' ', '___', '__']:
        field = field.replace(char, '_')
    return ''.join(x for x in str(field) if x.isalnum() or x == '_').lower()
