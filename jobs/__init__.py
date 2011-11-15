from paste.httpserver import serve
from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

import logging

log = logging.getLogger('job-server')

# PUT /jobs < $task-name > PID/UID
# POST /jobs/$UID/stdin < data
# GET /jobs/$UID/std[out|err] > data
# DELETE /jobs/$UID 



def main(global_config, **settings):

    config = Configurator(settings=settings)
    config.add_route('root', '/')

    config.scan()

    return config.make_wsgi_app()
