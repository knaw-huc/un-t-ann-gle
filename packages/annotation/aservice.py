import sys
sys.path.append('../packages')

from flask import Flask
from flask import jsonify
from flask import request
from flask import make_response
import json
from annotation import asearch
from segmentedtext import tservice

app = Flask(__name__)

annotations = ['eerste annotation', 'tweede annotation', 'derde annotation']

quarks = [{'name': 'up', 'charge': '+2/3'},
          {'name': 'down', 'charge': '-1/3'},
          {'name': 'charm', 'charge': '+2/3'},
          {'name': 'strange', 'charge': '-1/3'}]

@app.route('/annotations', methods=['GET', 'PUT'])
def get_annotations():
    if request.method == 'PUT':
        global annotations
        content = request.get_json()
        annotations = content
        res = make_response(jsonify({"message": "Annotations replaced"}), 200)
        return res
        
    return jsonify({'annotations': annotations})
    
@app.route('/annotations/<int:index>', methods=['GET'])
def get_annotation(index):
    return jsonify({'annotations': annotations[index]})

@app.route('/', methods=['GET'])
def identify_yourself():
    return jsonify({'message' : 'un-t-ann-gle Flask annotation service'})

@app.route('/annotations/<string:type>', methods=['GET'])
# REMARK: this is probably very inefficient because of copying of large lists
def returnAnnotationsOfType(type):
    annots = list(asearch.get_annotations_of_type(type,annotations))
    return jsonify({'annotations' : annots})
    
@app.route('/annotations/<string:begin_anchor>,<string:end_anchor>', methods=['GET'])
def returnAnnotationsOverlappingWith(begin_anchor, end_anchor):
    annots = list(asearch.get_annotations_overlapping_with(begin_anchor,end_anchor,annotations))
    return jsonify({'annotations' : annots})

@app.route('/quarks', methods=['POST'])
def addOne():
    new_quark = request.get_json()
    quarks.append(new_quark)
    return jsonify({'quarks' : quarks})

@app.route('/quarks/<string:name>', methods=['DELETE'])
def deleteOne(name):
    for i,q in enumerate(quarks):
      if q['name'] == name:
        del quarks[i]  
    return jsonify({'quarks' : quarks})
    
@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)

if __name__ == "__main__":
    app.run(debug=True)