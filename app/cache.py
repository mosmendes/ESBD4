
import os, time
import redis
from typing import Optional, Tuple

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
STREAM_NAME = os.getenv("STREAM_NAME", "wb:stream")

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def _version_key(key: str) -> str:
    return f"ver:{key}"

def set_write_back(key: str, value: str) -> int:
    """
       Write-back: Grava no cache imediatamente e enfileira no fluxo para persistência assíncrona.
       Retorna a versão usada para esta gravação.
    """
    # Gerar versão por chave
    version = r.incr(_version_key(key))
    # Gravar no cache (valor + versão juntos para leituras)
    pipe = r.pipeline()
    pipe.hset(f"cache:{key}", mapping={"value": value, "version": version})
    # Enfileirar alterações no fluxo (para o worker)
    pipe.xadd(STREAM_NAME, {"key": key, "value": value, "version": version, "ts": int(time.time() * 1000)})
    pipe.execute()
    return version

def get_from_cache(key: str) -> Optional[Tuple[Optional[str], Optional[int]]]:
    data = r.hgetall(f"cache:{key}")
    if not data:
        return None
    val = data.get("value")
    ver = int(data.get("version", 0)) if data.get("version") is not None else 0
    return val, ver
