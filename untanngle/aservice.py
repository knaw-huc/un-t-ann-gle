# NOTE: import of annotations currently assumes that the (json) store contains Anchor objects.
# That is only the case for SplittableSegmentedText, not for IndexedSegmentedText. The latter
# case will probably break with this code.

import sys

sys.path.append('../../packages')

from flask import Flask
from flask import jsonify
from flask import request
from flask import make_response
import json
from annotation import asearch
from textservice import segmentedtext

app = Flask(__name__)

app.json_encoder = segmentedtext.AnchorEncoder

# datadir = '../../data/1728/10mrt-v1/'
# datadir = '../../data/'
# annotation_repo = '1728-annotationstore-full.json'
datadir = '../../data/output/'
annotation_repo = 'tei_annotationstore.json'

annotations = []
anchors = {}

with open(datadir + annotation_repo, 'r') as filehandle:
    annotations = json.loads(filehandle.read())


# convert anchor dicts to unique Anchor instances, use anchors dict to
# 1. enforce uniqueness
# 2. easily map anchor identifiers to Anchor objects

def anchors_dict_2_obj(a):
    if isinstance(a['begin_anchor'], dict):
        ba_dict = a['begin_anchor']
        if anchors.get(ba_dict['identifier']) is None:
            anchors[ba_dict['identifier']] = segmentedtext.Anchor(ba_dict['identifier'], ba_dict['sequence_number'])
        a['begin_anchor'] = anchors[ba_dict['identifier']]

        ea_dict = a['end_anchor']
        if anchors.get(ea_dict['identifier']) is None:
            anchors[ea_dict['identifier']] = segmentedtext.Anchor(ea_dict['identifier'], ea_dict['sequence_number'])
        a['end_anchor'] = anchors[ea_dict['identifier']]


for a in annotations:
    anchors_dict_2_obj(a)


@app.route('/', methods=['GET'])
def identify_yourself():
    return jsonify({'message': 'un-t-ann-gle Flask annotation service'})


@app.route('/annotations', methods=['GET', 'PUT'])
def get_annotations():
    if request.method == 'PUT':
        global annotations
        # global anchors
        ann = request.get_json()

        # substitute json dict anchor with Anchor instance
        anchors_dict_2_obj(ann)

        annotations.append(ann)
        res = make_response(jsonify({"message": "Annotation appended"}), 200)
        return res

    return jsonify({'annotations': annotations})


@app.route('/annotations/<int:index>', methods=['GET'])
def get_annotation(index):
    return jsonify({'annotations': annotations[index]})


@app.route('/annotations/<string:identifier>', methods=['GET', 'DELETE'])
def returnAnnotationById(identifier):
    global annotations
    ann = asearch.get_annotation_by_id(identifier, annotations)
    if request.method == 'DELETE':
        annotations.remove(ann)
        res = make_response(jsonify({"message": "Annotation deleted"}), 200)
        return res

    return jsonify({'annotations': ann})


@app.route('/annotations/type/<string:type>', methods=['GET'])
# REMARK: this is probably very inefficient because of copying of large lists
def returnAnnotationsOfType(type):
    annots = list(asearch.get_annotations_of_type(type, annotations))
    return jsonify({'annotations': annots})


@app.route('/<string:resource_id>/annotations/<string:type>', methods=['GET'])
# REMARK: this is probably very inefficient because of copying of large lists
def returnAnnotationsOfTypeforResource(resource_id, type):
    annots = list(asearch.get_annotations_of_type(type, annotations, resource_id))
    return jsonify({'annotations': annots})


@app.route('/<string:resource_id>/annotations/<int:begin_anchor>,<int:end_anchor>', methods=['GET'])
def returnAnnotationsOverlappingWithInt(begin_anchor, end_anchor, resource_id):
    args = request.args
    #    annots = list(asearch.get_annotations_of_type_overlapping(args['type'], begin_anchor,end_anchor,annotations,resource_id))
    annots = list(
        asearch.get_filtered_annotations_overlapping(args, begin_anchor, end_anchor, annotations, resource_id))
    return jsonify({'annotations': annots})


@app.route('/<string:resource_id>/annotations/<string:begin_anchor_id>,<string:end_anchor_id>', methods=['GET'])
def returnAnnotationsOverlappingWithStr(begin_anchor_id, end_anchor_id, resource_id):
    begin_anchor = anchors[begin_anchor_id]
    end_anchor = anchors[end_anchor_id]
    annots = list(asearch.get_annotations_overlapping_with(begin_anchor, end_anchor, annotations, resource_id))
    return jsonify({'annotations': annots})


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
