class BooleanMessage:
    success = "tool_call_success"
    failure = "tool_call_failure"


class ToolResponse:
    @classmethod
    def success(cls, content: str | None):
        return {
            "success": True,
            "content": content,
        }

    @classmethod
    def failure(cls, content: str | None):
        return {
            "success": False,
            "content": content,
        }
