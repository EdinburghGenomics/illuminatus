#!python

"""
I want to permit dumping of OrderedDict and defaultdict with
yaml.safe_dump().
The OrderedDict will be dumped as a regular dict but in order.
I don't generally care about how the YAML is loaded.

As a new addition, defaultdict objects will also be dump-able as
regular dicts, sorted by key just like regular dicts.
This is handy where a defaultdict is embedded in an structure you
are dumping.

Both of these are lossy - you can restore neither the order of the
elements nor the special defaultdict behaviour.

To use it:

    from yaml_ordered import yaml

Then call yaml.safe_dump() etc. as normal. This used to just
monkey-patch the global YAML loader object but now it doesn't
do that any more - it uses yamlloader instead.

"""
import os
import yaml as real_yaml
import yamlloader
from collections import defaultdict

# So that calers can import and thus catch this exception
ParserError = real_yaml.parser.ParserError

class yaml:

    @classmethod
    def ordered_load(cls, *args, **kwargs):
        return real_yaml.load(*args, Loader=yamlloader.ordereddict.CSafeLoader, **kwargs)

    @classmethod
    def safe_load(cls, *args, **kwargs):
        return real_yaml.safe_load(*args, **kwargs)

    @classmethod
    def load(cls, *args, **kwargs):
        return real_yaml.safe_load(*args, **kwargs)

    @classmethod
    def safe_dump(cls, *args, **kwargs):
        return real_yaml.dump(*args, Dumper=yamlloader.ordereddict.CSafeDumper, **kwargs)

# Make all dicts be ordered on dump!
for t in dict, defaultdict:
    yamlloader.ordereddict.CSafeDumper.add_representer(t, yamlloader.ordereddict.CSafeDumper.represent_ordereddict)

def dictify(s):
    """Utility function to change all OrderedDict in a structure
       into a dict.
    """
    if any(isinstance(s, t) for t in [str, int, float, bool]):
        return s
    try:
        # Convert dict and dict-like things.
        return {k: dictify(v) for k, v in s.items()}
    except AttributeError:
        try:
            # List-like things that aren't strings
            return [ dictify(i) for i in s ]
        except Exception:
            # Give up and convert s to a str
            return str(s)

# YAML convenience functions that use the ordered loader/saver
# yamlloader is basically the same as my yaml_ordered hack. It should go away now that
# dict order is maintained, yet it persists.
def load_yaml(filename, dictify_result=False, relative_to=None):
    """Load YAML from a file (not a file handle).
    """
    if relative_to:
        filename = os.path.join(os.path.dirname(relative_to), filename)

    if getattr(filename, "read", None):
        # OK the filename is actually a file handle
        y = yaml.ordered_load(filename)
    else:
        # We are not interested in parsing a YAML string directly, open
        # the file.
        with open(filename) as yfh:
            y = yaml.ordered_load(yfh)

    return dictify(y) if dictify_result else y

def dump_yaml(foo, filename=None, fh=None, mode='w'):
    """Return YAML string and optionally dump to a file (or a file handle)."""
    ydoc = yaml.safe_dump(foo, default_flow_style=False)
    if fh:
        print(ydoc, file=fh, end='')
    if filename:
        with open(filename, mode) as yfh:
            print(ydoc, file=yfh, end='')
    return ydoc

