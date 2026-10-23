"""
A scripted stand-in for anthropic.Anthropic, so agent tests run offline.

Router calls and conversation calls are told apart by their system prompt and
served from separate queues, so a test can script each independently.
"""

import json
from types import SimpleNamespace as NS

from app.agent.prompts import ROUTER_PROMPT


class Block(NS):
    """Mimics an SDK content block, including to_dict()."""

    def to_dict(self, **_):
        return dict(vars(self))


def text(t):
    return Block(type="text", text=t)


def tool_use(name, args, id_="tu_1"):
    return Block(type="tool_use", name=name, input=args, id=id_)


def reply(stop_reason, *blocks):
    return NS(stop_reason=stop_reason, content=list(blocks))


def route(intent, confidence=0.95):
    return reply("end_turn", text(json.dumps({"intent": intent,
                                              "confidence": confidence})))


class FakeStream:
    """Mimics messages.stream(): text_stream + get_final_message()."""

    def __init__(self, response):
        self._response = response
        self.text_stream = (b.text for b in response.content
                            if getattr(b, "type", None) == "text")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._response


class FakeClient:
    def __init__(self, model=(), router=()):
        self._model = list(model)
        self._router = list(router)
        self.model_requests = []
        self.router_requests = []
        self.beta = NS(messages=NS(create=self._create, stream=self._stream))

    def _create(self, **kwargs):
        # Snapshot the messages list: the real code appends to it afterwards.
        snapshot = {**kwargs, "messages": list(kwargs["messages"])}
        if kwargs["system"] == ROUTER_PROMPT:
            self.router_requests.append(snapshot)
            return self._router.pop(0)
        self.model_requests.append(snapshot)
        return self._model.pop(0)

    def _stream(self, **kwargs):
        return FakeStream(self._create(**kwargs))
