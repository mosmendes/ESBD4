
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from cache import set_write_back, get_from_cache, r
from db import read_from_db

# Inicializa a aplicação FastAPI
app = FastAPI(title="Write-Back Cache API", version="1.0.0")

# Modelo de entrada (body) para as requisições POST
class Item(BaseModel):
    key: str
    value: str



# Endpoint para escrita no cache (write-back).
# Recebe chave e valor do usuário, Chama a função set_write_back(), que grava no Redis
# e dispara o evento para o worker persistir no banco depois.
# Retorna status de "cached", indicando que o valor foi salvo temporariamente no cache, junto com a versão.
@app.post("/set")
def set_value(item: Item):
    version = set_write_back(item.key, item.value)
    return {"status": "cached", "key": item.key, "value": item.value, "version": version}


# Endpoint para leitura de valores.
# Permite buscar dados no 'cache' (Redis) ou no 'db' (PostgreSQL).
    """
    - Se source="cache" (padrão):
        → Busca no Redis e retorna valor e versão.
        → Se não encontrado, retorna None.
    - Se source="db":
        → Busca diretamente no banco de dados.
        → Retorna valor e versão persistida.
    - Caso source seja diferente de 'cache' ou 'db',
      retorna erro HTTP 400.
    """
@app.get("/get/{key}")
def get_value(key: str, source: Optional[str] = "cache"):
    if source == "cache":
        res = get_from_cache(key)
        if res is None:
            return {"key": key, "value": None, "version": None, "source": "cache"}
        value, version = res
        return {"key": key, "value": value, "version": version, "source": "cache"}
    elif source == "db":
        row = read_from_db(key)
        if not row:
            return {"key": key, "value": None, "version": None, "source": "db"}
        value, version = row[0], int(row[1])
        return {"key": key, "value": value, "version": version, "source": "db"}
    else:
        raise HTTPException(status_code=400, detail="source must be 'cache' or 'db'")
