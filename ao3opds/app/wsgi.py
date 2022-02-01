''' Provides a convenient WSGI endpoint for running ao3opds.app. '''
from ao3opds.app.reverse_proxy import ReverseProxied
from ao3opds.app import create_app

app = create_app()
# Make the WSGI app reverse-proxy-aware:
app.wsgi_app = ReverseProxied(app.wsgi_app)

if __name__ == "__main__":
    app.run()
