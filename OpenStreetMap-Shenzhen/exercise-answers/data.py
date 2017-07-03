#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv
import codecs
import re
import xml.etree.cElementTree as ET
from audit import *

import cerberus

import schema

OSM_PATH = “example.osm"

NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

LOWER_COLON = re.compile(r'^([a-z]|_)+:([a-z]|_)+')
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

SCHEMA = schema.schema

# Make sure the fields order in the csvs matches the column order in the sql table schema
NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']


def shape_element(element, node_attr_fields=NODE_FIELDS, way_attr_fields=WAY_FIELDS,
                  problem_chars=PROBLEMCHARS, default_tag_type='regular'):
    """Clean and shape node or way XML element to Python dict"""

    node_attribs = {}
    way_attribs = {}
    way_nodes = []
    tags = []  # Handle secondary tags the same way for both node and way elements

    # YOUR CODE HERE
    if element.tag == 'node':
        for item in element.attrib:
            if item in NODE_FIELDS:
                node_attribs[item] = element.attrib[item]
        for child in element:
            node_tag = {}
            if PROBLEMCHARS.match(child.attrib['k']):
                continue
            elif LOWER_COLON.match(child.attrib['k']):
                node_tag["type"] = child.attrib["k"].split(":",2)[0]
                node_tag["key"] = child.attrib["k"].split(":",2)[1]
                node_tag["id"] = element.attrib["id"]
                node_tag["value"] = child.attrib["v"]
                tags.append(node_tag)
            else:
                node_tag["type"] = "regular"
                node_tag["key"] = child.attrib["k"]
                node_tag["id"] = element.attrib["id"]
                node_tag["value"] = child.attrib["v"]
                tags.append(node_tag)


        if node_attribs:
            return {'node': node_attribs, 'node_tags': tags}
        else:
            return none


    elif element.tag == 'way':
        for item in element.attrib:
            if item in WAY_FIELDS:
                way_attribs[item] = element.attrib[item]
        count = 0
        for child in element:
            if child.tag == "nd":
                way_node_dict = {}
                way_node_dict['id'] = element.attrib['id']
                if child.get('ref'):
                    way_node_dict["node_id"] = child.attrib['ref']
                    way_node_dict['position'] = count
                    count += 1
                way_nodes.append(way_node_dict)
            if child.tag == "tag":
                child.attrib['v'] = update_name(child.attrib['v'], mapping)
                way_tags = {}
                way_tags["id"] = element.attrib["id"]
                way_tags["value"] = child.attrib["v"]
                if PROBLEMCHARS.match(child.attrib['k']):
                    continue
                elif LOWER_COLON.match(child.attrib['k']):
                    if len(child.attrib['k'].split(":")) == 2:
                        way_tags["key"] = child.attrib["k"].split(":",2)[1]
                        way_tags["type"] = child.attrib["k"].split(":",2)[0]
                    elif len(child.attrib['k'].split(":")) == 3:
                        way_tags["key"] = child.attrib["k"].split(":",2)[1] + ":" + child.attrib["k"].split(":",2)[2]
                        way_tags["type"] = child.attrib["k"].split(":",2)[0]

                else:
                    way_tags["type"] = "regular"
                    way_tags["key"] = child.attrib["k"]
                    tags.append(way_tags)

        if way_attribs:
            return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}
        else:
            return none


# ================================================== #
#               Helper Functions                     #
# ================================================== #
def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag"""

    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()


def validate_element(element, validator, schema=SCHEMA):
    """Raise ValidationError if element does not match schema"""
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_strings = (
            "{0}: {1}".format(k, v if isinstance(v, str) else ", ".join(v))
            for k, v in errors.iteritems()
        )
        raise cerberus.ValidationError(
            message_string.format(field, "\n".join(error_strings))
        )


class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in row.iteritems()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# ================================================== #
#               Main Function                        #
# ================================================== #
def process_map(file_in, validate):
    """Iteratively process each XML element and write to csv(s)"""

    with codecs.open(NODES_PATH, 'w') as nodes_file, \
         codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file, \
         codecs.open(WAYS_PATH, 'w') as ways_file, \
         codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file, \
         codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)

        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()

        validator = cerberus.Validator()

        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)
            if el:
                if validate is True:
                    validate_element(el, validator)

                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])



if __name__ == '__main__':
    # Note: Validation is ~ 10X slower. For the project consider using a small
    # sample of the map when validating.
    process_map(OSM_PATH, validate=False)
