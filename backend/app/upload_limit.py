"""Bound multipart bodies before Starlette spools uploads to temporary storage."""
from fastapi.responses import Response
from app.config import MAX_UPLOAD


class UploadBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') != 'POST' or scope.get('path') != '/api/documents':
            return await self.app(scope, receive, send)
        # A bounded in-memory request copy allows rejection before multipart parsing.
        # Extra room covers multipart headers, not extra source-file bytes.
        limit = MAX_UPLOAD + 65536
        headers = dict(scope['headers'])
        try:
            claimed = int(headers.get(b'content-length', b'0'))
        except ValueError:
            return await Response('Invalid Content-Length', status_code=400)(scope, receive, send)
        if claimed > limit:
            return await Response('Upload exceeds size limit', status_code=413)(scope, receive, send)
        messages, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            size += len(message.get('body', b''))
            if size > limit:
                return await Response('Upload exceeds size limit', status_code=413)(scope, receive, send)
            messages.append(message)
            if not message.get('more_body', False):
                break
        iterator = iter(messages)

        async def replay():
            return next(iterator, {'type': 'http.request', 'body': b'', 'more_body': False})

        await self.app(scope, replay, send)
