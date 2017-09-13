#!python

# This comes from https://gist.github.com/nnemkin/2337410
# Tested on Python 2 and 3

"""
Patcher to permit dumping of OrderedDict with yaml.safe_dump().
The OrderedDict will be dumped as a regular dict but in order.
This will not affect how the YAML is loaded, nor how the OrderedDict
is represented with regular yaml.dump().

As a new addition, defaultdict objects will also be dump-able as
if they were regular dicts, sorted by key just like regular dicts.
This is handy where a defaultdict is embedded in an structure you
are dumping.

Both of these are lossy - you can restore neither the order of the
elements nor the special defaultdict behaviour.

To use it:

    from yaml_ordered import yaml

Then call yaml.safe_dump() etc. as normal.  Note that other modules that
import YAML will also get the patch, but since all it does is remove an
error case there should(!) be no impact.

"""

import yaml
from collections import OrderedDict, defaultdict
from yaml.nodes import MappingNode, ScalarNode


_YAML_MAP_TAG = 'tag:yaml.org,2002:map'

def _represent_ordered_dict(self, mapping, flow_style=None):
    value = []
    node = MappingNode(_YAML_MAP_TAG, value, flow_style=flow_style)
    if self.alias_key is not None:
        self.represented_objects[self.alias_key] = node
    best_style = True
    if hasattr(mapping, 'items'):
        mapping = mapping.items()
    for item_key, item_value in mapping:
        node_key = self.represent_data(item_key)
        node_value = self.represent_data(item_value)
        if not (isinstance(node_key, ScalarNode) and not node_key.style):
            best_style = False
        if not (isinstance(node_value, ScalarNode) and not node_value.style):
            best_style = False
        value.append((node_key, node_value))
    if flow_style is None:
        if self.default_flow_style is not None:
            node.flow_style = self.default_flow_style
        else:
            node.flow_style = best_style
    return node

# I only care about this one case!
yaml.SafeDumper.add_representer(OrderedDict, _represent_ordered_dict)

# Oh, and this one...
yaml.SafeDumper.add_representer(defaultdict, yaml.representer.SafeRepresenter.represent_dict)

# Tests are now moved to test/test_yaml_ordered where they belong
