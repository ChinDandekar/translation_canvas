# cli.py

import click
from translation_canvas.app import create_app

@click.command()
@click.option('--host', default='127.0.0.1', help='The interface to bind to.')
@click.option('--port', default=5000, help='The port to bind to.')
@click.option('--debug', default=False, help='Enable debug mode.')
def start_server(host, port, debug):
    """Starts the Flask server."""
    create_app().run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    start_server()
