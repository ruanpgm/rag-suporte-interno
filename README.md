# rag-suporte-interno

Agente de suporte N1 que responde sobre a base interna de soluções e **abre chamado sozinho quando não resolve**.

> Reimplementação pública de um sistema que mantenho em produção. A base aqui é sintética: 12 artigos de suporte escritos para o exemplo.

## O problema

A equipe de TI responde os mesmos vinte problemas o dia inteiro. Pior que o tempo: metade chega por mensagem solta ou pessoa parando no corredor — sem chamado, sem SLA, **sem histórico**. E sem histórico não dá para saber o que corrigir na raiz.

## Rodando

```bash
python3 agente.py --demo     # três casos: resolve, escala, e se recusa a responder
python3 agente.py            # interativo
```

Só stdlib. Sem chave de API, sem Docker, sem instalar nada.

```
  usuário: não consigo acessar a rede nem a pasta compartilhada

  agente (1/3) · Pasta de rede não abre mais  [sim 0.50]
     1. Confira se outras pastas do mesmo servidor abrem.
     ...
  usuário: n

  agente (2/3) · Excel travando em planilha compartilhada  [sim 0.25]
  usuário: n

  agente (3/3) · Conta bloqueada no domínio  [sim 0.13]
  usuário: n

  agente: 3 tentativas sem sucesso. Abrindo chamado.
  → chamado_20260915_060205_814759.json
```

O chamado sobe com o que já foi tentado anexado — o analista humano não recomeça do zero.

## Decisões

**RAG, não fine-tuning.** A base muda toda semana. Fine-tuning exigiria retreinar a cada mudança e não permitiria citar a fonte — e em suporte o usuário precisa poder conferir de onde saiu a resposta. Com RAG, atualizar conhecimento é um insert.

**Busca atrás de uma interface.** Aqui a implementação é TF-IDF em memória, para o repo rodar sem infraestrutura. Em produção a mesma interface é atendida por pgvector: os artigos já viviam no Postgres, e subir um banco vetorial ao lado seria mais um sistema para operar e sincronizar sem ganho nesta escala — dezenas de artigos, não milhões de vetores. Cem vezes maior, a decisão muda; por isso está atrás de interface.

**Uma solução por vez, em botões.** Não é decisão de IA, é de produto — e foi a que mais mudou o resultado. Manual inteiro na tela faz o usuário desistir na terceira linha e chamar o humano, que era o que se queria evitar. Efeito colateral que virou o mais valioso: cada "não resolveu" é dado rotulado sobre qual artigo está ruim.

**Escalona em 3 tentativas.** Sem limite o agente entra em loop e o usuário perde a confiança na ferramenta inteira, inclusive onde ela funcionava.

**Chunk por artigo, não por tamanho fixo.** Artigo de suporte já é unidade semântica; cortar em N tokens parte o passo 3 do procedimento ao meio e recupera meia instrução — pior que não recuperar nada.

**Ele pode dizer "não sei".** Abaixo do limiar de similaridade não responde, vai direto para o chamado. Sem isso devolve sempre o artigo menos ruim — e em suporte resposta confiante e errada custa mais que resposta nenhuma: o usuário executa, não funciona, e agora tem um problema a mais.

## Resultado

O número do relatório é tempo de atendimento. O ganho real é outro: **conversa de corredor virou chamado registrado** — e chamado registrado é dado para ordenar por frequência, achar os três problemas que geram um terço do volume e corrigir a causa.

## Stack

Python (stdlib) · TF-IDF + cosseno na versão local · pgvector em produção

MIT
