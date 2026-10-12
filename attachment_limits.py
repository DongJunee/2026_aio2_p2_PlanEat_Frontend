"""대화 전체에 적용하는 이미지 첨부 한도."""

MAX_SESSION_IMAGES = 5


def remaining_image_slots(messages):
    """응답 실패 여부와 관계없이 이미 전송한 사용자 이미지를 센다."""
    used = sum(
        len(message.get("images") or [])
        for message in messages
        if message.get("role") == "user"
    )
    return max(0, MAX_SESSION_IMAGES - used)
