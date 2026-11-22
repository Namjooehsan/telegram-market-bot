import json

from buffer_integration import BufferAPIError, BufferClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, headers, json, timeout):
        self.calls.append({"url": url, "headers": headers, "body": json, "timeout": timeout})
        query = json["query"]
        if "GetOrganizations" in query:
            return FakeResponse({"data": {"account": {"organizations": [{"id": "org-1", "name": "NOVA"}]}}})
        if "GetChannels" in query:
            return FakeResponse({"data": {"channels": [{
                "id": "channel-1", "name": "@nova", "displayName": "NOVA Page",
                "service": "facebook", "descriptor": "Facebook Page",
                "isDisconnected": False, "isLocked": False, "isQueuePaused": False
            }]}})
        if "CreateQueuedPost" in query:
            return FakeResponse({"data": {"createPost": {"post": {"id": "post-1", "dueAt": "2026-11-23T10:00:00Z"}}}})
        raise AssertionError("Unexpected GraphQL operation")


def test_buffer_lists_connected_channels_and_queues_post():
    session = FakeSession()
    client = BufferClient("test-api-key", session=session)

    channels = client.list_channels()
    post = client.create_post("channel-1", "سلام بازار")

    assert channels[0]["id"] == "channel-1"
    assert channels[0]["organizationName"] == "NOVA"
    assert post["id"] == "post-1"
    assert all(call["url"] == "https://api.buffer.com" for call in session.calls)
    assert all(call["headers"]["Authorization"] == "Bearer test-api-key" for call in session.calls)
    assert "سلام بازار" in session.calls[-1]["body"]["query"]


def test_buffer_requires_api_key():
    try:
        BufferClient("")
    except BufferAPIError as exc:
        assert "BUFFER_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing API key to fail closed")


def test_buffer_graphql_auth_errors_are_reported_without_secret():
    session = FakeSession()
    session.post = lambda *args, **kwargs: FakeResponse({
        "errors": [{"message": "Not authorized", "extensions": {"code": "UNAUTHORIZED"}}]
    })
    client = BufferClient("do-not-print-this", session=session)
    try:
        client.list_channels()
    except BufferAPIError as exc:
        assert "Not authorized" in str(exc)
        assert "do-not-print-this" not in str(exc)
    else:
        raise AssertionError("Expected GraphQL auth error")
