
# Write-Back Cache (Redis + FastAPI + Postgres)

Arquitetura:
- **API (FastAPI)**: escreve no Redis (cache) e envia evento para um *Redis Stream* (write-back assíncrono).
- **Worker**: consome o stream, faz *coalescing* por chave (última versão vence) e persiste no Postgres.
- **Postgres**: armazena `key, value, version` com UPSERT protegido por versão (last-write-wins).
- **Redis**: também mantém o valor + versão no cache (`HSET cache:{key}`) para leituras rápidas.


## Como lidamos com concorrência e integridade

- **Versão por chave**: cada escrita faz `INCR ver:{key}` e carrega `version` no evento e no cache.
- **ConcorrÊncia no Worker**: ao consumir um lote, o worker só persiste a maior `version` por `key` (última escrita vence).
- **Redis Streams + Consumer Group**: garante ordenação por stream e reprocessamento seguro em caso de falhas (pendentes).
- **Separação API/Worker**: falhas no banco não afetam a latência de escrita da API.

### Limitações do Write-Back
- Risco de perda de dados se Redis falhar antes da persistência (mitigado parcialmente com AOF `appendonly yes`).
- Maior complexidade operacional (stream, worker, versionamento).
- Banco pode ficar defasado (consistência eventual).

## Quando usar (exemplos)
- **Não recomendado**: operações financeiras, controle de estoque, pedidos — onde perda/ordem de gravação é crítica.
- **Recomendado**: telemetria, métricas de uso, contadores de visualização, preferências temporárias — prioriza latência.

