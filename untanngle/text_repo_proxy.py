#!/usr/bin/env python3

import werkzeug
from flask import Flask

werkzeug.cached_property = werkzeug.utils.cached_property
import uuid
from flask_restplus import Api, Resource, fields

title = "TextRepo Proxy"
version = "0.0.1"

app = Flask(__name__)
api = Api(app,
          version=version,
          title=title,
          description='Proxy of TextRepo. For experimental use only. Data is only stored in-memory.'
          )


@api.route('/about')
class About(Resource):
    def get(self):
        return {"title": title, "version": version}


texts = {}

texts_ns = api.namespace('texts', description='text operations')

text_payload = api.model('Text', {'text': fields.String(required=True, description='The text to store')})


class TextDAO(object):
    def __init__(self):
        self.texts = {}

    def get(self, id):
        if id in texts.keys():
            return texts[id]
        api.abort(404, "Text {} doesn't exist".format(id))

    def create(self, data):
        id = uuid.uuid4()
        self.texts[id] = data
        return id

    def update(self, id, data):
        prev = texts[id]
        self.texts[id] = data
        return prev

    def delete(self, id):
        self.texts.remove(id)


DAO = TextDAO()


@texts_ns.route('/')
class Texts(Resource):
    '''Shows a list of all text ids'''

    def get(self):
        return list(texts.keys())

    @texts_ns.expect(text_payload)
    @texts_ns.marshal_with(text_payload, code=201)
    def post(self):
        return DAO.create(api.payload), 201


@texts_ns.route('/<uuid>')
class Text(Resource):
    '''Show a single text item'''

    def get(self, uuid):
        return DAO.get(uuid)


if __name__ == "__main__":
    app.run(debug=True)
