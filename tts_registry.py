"""
로컬 TTS 서버 URL 레지스트리 (Cloudtype 프로세스 내 공유 상태)

로컬 PC 가 quick tunnel 을 새로 띄울 때마다 그 URL 을 /tts/register 로 보내오면
여기에 저장한다. arona_voice.speak() 는 env 고정값 대신 이 값을 사용한다.

- Flask(waitress 스레드)의 등록 핸들러와 봇(asyncio)의 speak() 가 같은 프로세스에서
  이 모듈을 공유하므로 module-level 변수 + Lock 으로 충분하다.
- Cloudtype 재시작 시 메모리가 비므로, 로컬이 주기적으로(heartbeat) 재등록한다.
"""

import time
import threading

_lock = threading.Lock()
_url = None
_updated_at = 0.0

# 등록 후 이 시간(초)이 지나면 stale 로 간주 (로컬/터널이 죽은 것으로 판단)
TTL_SECONDS = 180


def set_url(url: str):
    global _url, _updated_at
    with _lock:
        _url = (url or "").strip() or None
        _updated_at = time.time()


def get_url():
    """유효(신선)한 등록 URL 을 반환. 없거나 오래됐으면 None."""
    with _lock:
        if not _url:
            return None
        if time.time() - _updated_at > TTL_SECONDS:
            return None
        return _url


def status():
    with _lock:
        age = time.time() - _updated_at if _url else None
        return {
            "url": _url,
            "age_seconds": round(age, 1) if age is not None else None,
            "fresh": (_url is not None and age is not None and age <= TTL_SECONDS),
        }
