import sys

sys.path.append('../../packages')

from flask import Flask
from flask import jsonify
from flask import make_response
import json

app = Flask(__name__)

from textservice import segmentedtext

app.json_encoder = segmentedtext.SegmentEncoder

datadir = '../../data/1728/10mrt-v1/'
text_repo = '1728-textstore.json'
# datadir = '../../data/output/'
# text_repo = 'tei_textstore.json'

text_resources = []

with open(datadir + text_repo, 'r') as filehandle:
    data = json.loads(filehandle.read())
    for res in data['_resources']:
        if '_anchors' in res:
            text_resources.append(segmentedtext.SplittableSegmentedText.from_json(res))
        else:
            text_resources.append(segmentedtext.IndexedSegmentedText.from_json(res))


def get_segmentedtext_for(resource_id):
    return [st for st in text_resources if st.resource_id == resource_id][0]


@app.route('/', methods=['GET'])
def identify_yourself():
    return jsonify({'message': 'un-t-ann-gle Flask text service'})


@app.route('/resources', methods=['GET'])
def return_resources():
    resources = [st.resource_id for st in text_resources]
    return jsonify({'resources': resources})


@app.route('/<string:resource_id>/segmentedtext', methods=['GET'])
def return_segmentedtext(resource_id):
    return jsonify({'segmentedtext': get_segmentedtext_for(resource_id)})


@app.route('/<string:resource_id>/segmentedtext/length', methods=['GET'])
def return_text_len(resource_id):
    len = get_segmentedtext_for(resource_id).len()
    return jsonify({'length': len})


@app.route('/<string:resource_id>/segmentedtext/<string:anchor_id>', methods=['GET'])
def return_text__at(resource_id, anchor_id):
    text = get_segmentedtext_for(resource_id).element_at(anchor_id)
    return jsonify({'segment': text})


@app.route('/<string:resource_id>/segmentedtext/text/<string:begin_anchor_id>,<string:end_anchor_id>', methods=['GET'])
def return_text_segmentStr(resource_id, begin_anchor_id, end_anchor_id):
    text_segment = get_segmentedtext_for(resource_id).slice(begin_anchor_id, end_anchor_id)
    return jsonify({'text': text_segment})


@app.route('/<string:resource_id>/segmentedtext/textgrid/<string:begin_anchor_id>,<string:end_anchor_id>',
           methods=['GET'])
def return_text_gridStr(resource_id, begin_anchor_id, end_anchor_id):
    text_segment = get_segmentedtext_for(resource_id).slice_grid(begin_anchor_id, end_anchor_id)
    return jsonify({'text_grid': text_segment})


@app.route('/<string:resource_id>/segmentedtext/text/<int:begin_anchor>,<int:end_anchor>', methods=['GET'])
def return_text_segmentInt(resource_id, begin_anchor, end_anchor):
    text_segment = get_segmentedtext_for(resource_id).slice(begin_anchor, end_anchor)
    return jsonify({'text': text_segment})


@app.route('/<string:resource_id>/segmentedtext/textgrid/<int:begin_anchor>,<int:end_anchor>', methods=['GET'])
def return_text_gridInt(resource_id, begin_anchor, end_anchor):
    text_segment = get_segmentedtext_for(resource_id).slice_grid(begin_anchor, end_anchor)
    return jsonify({'textgrid': text_segment})


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
