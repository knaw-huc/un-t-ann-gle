#!/usr/bin/env python3
import werkzeug
from flask import Flask

werkzeug.cached_property = werkzeug.utils.cached_property
import uuid
from flask_restplus import Api, Resource

title = "WebAnnotationServer Proxy"
version = "0.0.1"

app = Flask(__name__)
api = Api(app,
          version=version,
          title=title,
          description='WebAnnotationServer Proxy. For experimental use only. Data is only stored in-memory.'
          )


@api.route('/about')
class About(Resource):
    def get(self):
        return {"title": title, "version": version}


annotation_ns = api.namespace('annotations', description='annotation operations')


class AnnotationDAO(object):
    def __init__(self):
        self.annotations = {}

    def get(self, id):
        if id in self.annotations.keys():
            return self.annotations[id]
        api.abort(404, "Annotation {} doesn't exist".format(id))

    def create(self, data):
        id = uuid.uuid4()
        self.annotations[id] = data
        return id

    def update(self, id, data):
        prev = self.annotations[id]
        self.annotations[id] = data
        return prev

    def delete(self, id):
        self.annotations.remove(id)


dao = AnnotationDAO()


@annotation_ns.route('/')
class Annotations(Resource):
    '''Shows a list of all annotation ids'''

    def get(self):
        return dao.annotations

    def post(self):
        data = self.api.payload
        return self.api.payload
        # return dao.create(data), 201


@annotation_ns.route('/<uuid>')
class Annotation(Resource):
    '''Show a single annotation'''

    def get(self, uuid):
        return dao.get(uuid)


if __name__ == "__main__":
    app.run(debug=True)
