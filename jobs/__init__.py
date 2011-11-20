from gevent import monkey; monkey.patch_all()
from gevent.pywsgi import WSGIServer 

from pyramid.config import Configurator

import logging

log = logging.getLogger(__name__)

def main(global_config, **settings):

    config = Configurator(settings=settings)

    config.add_static_view('static', 'jobs:static')

    config.add_route('root', '/')
    config.add_route('jobs', '/jobs')
    config.add_route('job', '/jobs/{uid}')
    config.add_route('job-stdout', '/jobs/{uid}/stdout')
    config.add_route('job-stderr', '/jobs/{uid}/stderr')
    config.add_route('job-stdin', '/jobs/{uid}/stdin')

    config.scan()

    return config.make_wsgi_app()

def server_runner(app, global_conf, host, port, spawn='default', **kwargs): 
    WSGIServer((host, int(port)), app).serve_forever()
