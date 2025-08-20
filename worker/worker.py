
import os
import time
import redis
from collections import defaultdict
from typing import Dict, Tuple, List
from db import write_to_db
from tenacity import retry, wait_fixed, stop_after_attempt

# Configuração das variáveis de ambiente para conexão com o Redis e controle do stream
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
STREAM_NAME = os.getenv("STREAM_NAME", "wb:stream")
STREAM_GROUP = os.getenv("STREAM_GROUP", "wb")
CONSUMER_NAME = os.getenv("CONSUMER_NAME", "worker-1")

# Conexão com o Redis
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Garante que o grupo de consumidores do stream exista.
def ensure_group():
    try:
        r.xgroup_create(STREAM_NAME, STREAM_GROUP, id="$", mkstream=True)
        print(f"Created group {STREAM_GROUP} on stream {STREAM_NAME}")
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" in str(e):
            pass
        else:
            raise

 
 # Processa um lote de mensagens lidas do stream Redis.
 # Consolida múltiplas atualizações da mesma chave, mantendo apenas a versão mais recente 
 # persiste os dados no banco de dados via função write_to_db.
@retry(wait=wait_fixed(2), stop=stop_after_attempt(10))
def process_batch(messages: List[Tuple[str, Dict[str, str]]]):
    # Coalesce by key, keep highest version (last-write-wins)
    latest: Dict[str, Tuple[str, int]] = {}
    for msg_id, fields in messages:
        key = fields["key"]
        value = fields["value"]
        version = int(fields["version"])
        if key not in latest or version >= latest[key][1]:
            latest[key] = (value, version)

    # Persist to DB
    for key, (value, version) in latest.items():
        write_to_db(key, value, version)

    
# Função principal do worker:
# Garante a criação do grupo de consumidores no Redis.
# Fica em loop contínuo lendo mensagens do stream.
def main():
    ensure_group()
    while True:
        # Lê primeiro mensagens pendentes, depois novas.
        resp = r.xreadgroup(groupname=STREAM_GROUP, consumername=CONSUMER_NAME,
                            streams={STREAM_NAME: ">"}, count=100, block=5000)
        if not resp:
            continue
        # resp format: [(stream, [(id, {fields}), ...])]
        for stream, entries in resp:
            try:
                process_batch(entries)
                # Confirma (ACK) que as mensagens foram processadas,
                # evitando que sejam reprocessadas no futuro.
                for msg_id, _ in entries:
                    r.xack(STREAM_NAME, STREAM_GROUP, msg_id)
            except Exception as e:
                # Em caso de falha, imprime o erro e aguarda 2s.
                # As mensagens não recebem ACK, permanecendo pendentes.
                print("Error processing batch:", e)
                time.sleep(2)

if __name__ == "__main__":
    main()
