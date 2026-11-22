"""Small, secret-safe client for Buffer's current GraphQL API."""
import requests


BUFFER_ENDPOINT = "https://api.buffer.com"


class BufferAPIError(RuntimeError):
    """Raised when Buffer rejects a request or returns a GraphQL error."""


class BufferClient:
    def __init__(self, api_key, session=None, timeout=20):
        self.api_key = (api_key or "").strip()
        self.session = session or requests.Session()
        self.timeout = timeout
        if not self.api_key:
            raise BufferAPIError("BUFFER_API_KEY is not configured")

    def _request(self, query):
        try:
            response = self.session.post(
                BUFFER_ENDPOINT,
                headers={
                    "Authorization": "Bearer " + self.api_key,
                    "Content-Type": "application/json",
                },
                json={"query": query},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise BufferAPIError("Buffer network request failed: " + str(exc)[:180]) from exc
        except ValueError as exc:
            raise BufferAPIError("Buffer returned invalid JSON") from exc

        errors = payload.get("errors") or []
        if errors:
            messages = [str(item.get("message") or "GraphQL error") for item in errors[:3]]
            raise BufferAPIError("Buffer API error: " + "; ".join(messages)[:300])
        data = payload.get("data")
        if not isinstance(data, dict):
            raise BufferAPIError("Buffer response did not contain data")
        return data

    def list_channels(self):
        organizations = self._request(
            "query GetOrganizations { account { organizations { id name } } }"
        ).get("account", {}).get("organizations") or []
        channels = []
        channel_query_template = """
        query GetChannels {
          channels(input: { organizationId: "%s" }) {
            id
            name
            displayName
            service
            descriptor
            isDisconnected
            isLocked
            isQueuePaused
          }
        }
        """
        for organization in organizations:
            organization_id = str(organization.get("id") or "")
            if not organization_id:
                continue
            query = channel_query_template % organization_id.replace('"', '')
            rows = self._request(query).get("channels") or []
            for channel in rows:
                item = dict(channel)
                item["organizationId"] = organization_id
                item["organizationName"] = organization.get("name") or ""
                channels.append(item)
        return channels

    def create_post(self, channel_id, text):
        import json

        channel_literal = json.dumps(str(channel_id))
        text_literal = json.dumps(str(text), ensure_ascii=False)
        query = """
        mutation CreateQueuedPost {
          createPost(input: {
            text: %s
            channelId: %s
            schedulingType: automatic
            mode: addToQueue
          }) {
            ... on PostActionSuccess {
              post { id dueAt }
            }
            ... on MutationError {
              message
            }
          }
        }
        """ % (text_literal, channel_literal)
        payload = self._request(query).get("createPost") or {}
        if payload.get("message"):
            raise BufferAPIError("Buffer could not queue the post: " + str(payload["message"])[:240])
        post = payload.get("post")
        if not isinstance(post, dict) or not post.get("id"):
            raise BufferAPIError("Buffer did not confirm post creation")
        return post
