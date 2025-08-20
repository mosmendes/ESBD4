
# Write-Back Cache (Redis + FastAPI + Postgres)

Arquitetura:
- **API (FastAPI)**: escreve no Redis (cache) e envia evento para um *Redis Stream* (write-back assíncrono).
- **Worker**: consome o stream, faz *coalescing* por chave (última versão vence) e persiste no Postgres.
- **Postgres**: armazena `key, value, version` com UPSERT protegido por versão (last-write-wins).
- **Redis**: também mantém o valor + versão no cache (`HSET cache:{key}`) para leituras rápidas.

## Subindo o ambiente

```bash
docker compose up --build
```

A API ficará em `http://localhost:8000`.

### Testes rápidos

1) **Escrita (write-back)**
```bash
curl -X POST http://localhost:8000/set -H "Content-Type: application/json" -d '{"key":"user:42","value":"Alice"}'
```

2) **Leitura do cache**
```bash
curl http://localhost:8000/get/user:42?source=cache
```

3) **Leitura do banco (pode demorar alguns segundos até o worker gravar)**
```bash
curl http://localhost:8000/get/user:42?source=db
```

4) **Condições de corrida**
Envie duas escritas rápidas para a mesma key; a de maior `version` prevalece:
```bash
curl -X POST http://localhost:8000/set -H "Content-Type: application/json" -d '{"key":"user:42","value":"A"}'
curl -X POST http://localhost:8000/set -H "Content-Type: application/json" -d '{"key":"user:42","value":"B"}'
# Leia do DB depois de alguns segundos, valor final deve ser "B"
curl http://localhost:8000/get/user:42?source=db
```

## Como lidamos com concorrência e integridade

- **Versão por chave (monotônica)**: cada escrita faz `INCR ver:{key}` e carrega `version` no evento e no cache.
- **Coalescing no Worker**: ao consumir um lote, o worker só persiste a maior `version` por `key` (última escrita vence).
- **UPSERT com guarda de versão**: `WHERE EXCLUDED.version >= cache_data.version` impede regressão no banco.
- **Redis Streams + Consumer Group**: garante ordenação por stream e reprocessamento seguro em caso de falhas (pendentes).
- **Separação API/Worker**: falhas no banco não afetam a latência de escrita da API.

### Limitações do Write-Back
- Risco de perda de dados se Redis falhar antes da persistência (mitigado parcialmente com AOF `appendonly yes`).
- Maior complexidade operacional (stream, worker, versionamento).
- Banco pode ficar defasado (consistência eventual).

## Quando usar (exemplos)
- **Não recomendado**: operações financeiras, controle de estoque, pedidos — onde perda/ordem de gravação é crítica.
- **Recomendado**: telemetria, métricas de uso, contadores de visualização, preferências temporárias — prioriza latência.

## Extras
- Você pode trocar Postgres por SQLite ou MySQL ajustando a string de conexão.
- Para aumentar throughput, escale `worker` (mas aí implemente locks por chave — ex.: `SETNX lock:{key}`).
