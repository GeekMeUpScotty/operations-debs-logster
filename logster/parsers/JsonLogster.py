###  JsonLogster parses a file of JsonObjects, each on their own line.
###  The object will be traversed, and each leaf node of the object will
###  be keyed by a concatenated key made up of all parent keys.
###
###  For example:
###  sudo ./logster --dry-run --output=ganglia --parser-options '--key-separator _' JsonLogster /var/cache/stats.log.json
###
import json
import optparse

from logster.logster_helper import MetricObject, LogsterParser
from logster.logster_helper import LogsterParsingException

class JsonLogster(LogsterParser):
    '''
    JsonLogster parses a file of JsonObjects, each on their own line.
    The object will be traversed, and each leaf node of the object will
    be keyed by a concatenated key made up of all parent keys.
    You can subclass this class and implement the key_filter method
    to skip or transform specific keys in the object hierarchy.
    '''

    def __init__(self, option_string=None):
        '''Initialize any data structures or variables needed for keeping track
        of the tasty bits we find in the log we are parsing.'''
        self.metrics = {}

        if option_string:
            options = option_string.split(' ')
        else:
            options = []

        optparser = optparse.OptionParser()
        optparser.add_option('--key-separator', '-k', dest='key_separator', default='.',
        help='Key separator for flattened json object key name. Default: \'.\'  \'/\' is not allowed.''')

        opts, args = optparser.parse_args(args=options)
        self.key_separator = opts.key_separator

    def key_filter(self, key):
        '''
        Default key_filter method.  Override and implement
        this method if you want to do any filtering or transforming
        on specific keys in your JSON object.
        '''
        return key

    def flatten_object(self, node, separator='.', key_filter_callback=None, parent_keys=[]):
        '''
        Recurses through dicts and/or lists and flattens them
        into a single level dict of key: value pairs.  Each
        key consists of all of the recursed keys joined by
        separator.  If key_filter_callback is callable,
        it will be called with each key.  It should return
        either a new key which will be used in the final full
        key string, or False, which will indicate that this
        key and its value should be skipped.
        '''
        flattened = {}

        try:
            iterator = node.iteritems()
        except AttributeError:
            iterator = enumerate(node)

        for key, child in iterator:
            # If key_filter_callback was provided,
            # then call it on the key.  If the returned
            # key is false, then, we know to skip it.
            if callable(key_filter_callback):
                key = key_filter_callback(key)
            if key is False:
                continue
            # '/' is  not allowed in key names.
            # Ganglia writes files based on key names
            # and doesn't escape these in the path.
            key = key.replace('/', self.key_separator)

            if hasattr(child, '__iter__'):
                # merge the child items all together
                flattened.update(self.flatten_object(child, separator, key_filter_callback, parent_keys + [str(key)]))
            else:
                final_key = separator.join(parent_keys + [str(key)])
                flattened[final_key] = child

        return flattened

    def parse_line(self, line):
        '''This function should digest the contents of one line at a time, updating
        object's state variables. Takes a single argument, the line to be parsed.'''

        json_data = json.loads(line)
        # Using update() in order to work with multiple lines.
        # Since lines are parsed in order as they appear in the file,
        # if there are multiple entries for the same key, this will
        # end up using the latest value for that key.
        self.metrics.update(self.flatten_object(json.loads(line), self.key_separator, self.key_filter))

    def get_state(self, duration):
        '''Run any necessary calculations on the data collected from the logs
        and return a list of metric objects.'''
        self.duration = duration

        metric_objects = []
        for metric_name, metric_value in self.metrics.items():
            if isinstance(metric_value, float):
                metric_type = 'float'
            elif isinstance(metric_value, int) or isinstance(metric_value, long):
                # bool is a subclass of int.  If metric_value
                # is a bool, then convert it to its integer value.
                if isinstance(metric_value, bool):
                    metric_value = int(metric_value)
                metric_type = 'int32'
            else:
                metric_type = 'string'
                metric_value = str(metric_value)

            metric_objects.append(MetricObject(metric_name, metric_value, type=metric_type))

        return metric_objects

