# resty.py, gekopieerd uit Python Cookbook, recipe 11.5

import cgi

def notfound_404(environ, start_response):
    start_response('404 Not Found', [('Content-type', 'text/plain')])
    return [b'Not found']
    
class PathDispatcher:
    def __init__(self):
        self.pathmap = {}
        
    def __call__(self, environ, start_response):
        path = environ['PATH_INFO']
        print(path)
        params = cgi.FieldStorage(environ['wsgi.input'], environ=environ)
        method = environ['REQUEST_METHOD'].lower()
        print(method)
        environ['params'] = {key: params.getvalue(key) for key in params}
        handler = self.pathmap.get((method,path), notfound_404)
        print(handler)
        return handler(environ, start_response)
        
    def register(self, method, path, function):
        print(f"register method: {method}, path: {path}, function: {function}")
        self.pathmap[method.lower(), path] = function
        print(self.pathmap)
        return function