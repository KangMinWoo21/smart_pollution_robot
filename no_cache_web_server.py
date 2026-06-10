from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
import argparse


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--directory', default='web_ui')
    args = parser.parse_args()

    handler = partial(NoCacheHandler, directory=args.directory)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f'Serving {args.directory} at http://{args.host}:{args.port} with no-cache headers')
    server.serve_forever()


if __name__ == '__main__':
    main()
