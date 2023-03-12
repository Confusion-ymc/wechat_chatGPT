from starlette.requests import Request


class AppState:
    def __init__(self, query_state: str):
        self.query_state = query_state

    def __call__(self, request: Request):
        if self.query_state:
            return getattr(request.app.state, self.query_state, None)
        return request.app.state
