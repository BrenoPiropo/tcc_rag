# RAG dos Anais da Semana de Iniciação Científica da UESC

Projeto do TCC para construir um sistema de geração aumentada por recuperação
(Retrieval-Augmented Generation, RAG) sobre os PDFs dos Anais da SIC/UESC.

## Estado atual: RAG local com LLM e consultas em grafo

Foi validada a fundação do banco:

- PostgreSQL 17;
- extensão pgvector 0.8.7;
- volume persistente para o banco;
- verificação automática de disponibilidade;
- script mínimo que habilita a extensão `vector`.

Resultados observados em 11 de novembro de 2026:

- contêiner em estado `healthy`;
- PostgreSQL 17.11;
- pgvector 0.8.7;
- acesso restrito a `127.0.0.1:25432`;
- três vetores conhecidos armazenados e comparados corretamente;
- os três vetores permaneceram após a reinicialização do contêiner.

Após a aprovação da amostra controlada, a extração integral processou os 3.969
documentos e as 3.970 páginas. Todas as páginas produziram texto, sem erro,
página vazia ou indicação automática de OCR. Os resultados foram importados e
validados no PostgreSQL. Após a aprovação da amostra, a segmentação integral
produziu 7.276 fragmentos rastreáveis para as 3.970 páginas. Foi gerada e
validada uma amostra de 25 embeddings BGE-M3 com 1.024 dimensões, cinco por
edição. Em seguida, os 7.276 fragmentos foram vetorizados, importados e validados
no pgvector. A interface local de recuperação semântica e avaliação humana foi
implementada e validada. Uma linha de base completa de RAG foi integrada ao
Ollama com o modelo local `llama3:latest`. O sistema recupera evidências,
elimina documentos e títulos duplicados do contexto, gera uma resposta fundamentada
e registra toda a configuração no PostgreSQL. Título, autor principal, orientador e
edição são obtidos deterministicamente do corpus e apresentados antes da síntese.
O orientador é associado ao nome numerado no cabeçalho que contém a indicação
`Orientador(a)`, impedindo que referências internas sejam tratadas como autoria ou
orientação do trabalho. A otimização
e a avaliação sistemática ainda serão executadas durante o TCC.

A auditoria do corpus confirmou 3.969 PDFs estruturalmente legíveis, 3.970 páginas,
nenhum arquivo ausente, nenhuma duplicata por SHA-256 e nenhum erro crítico.

Em 21 de novembro de 2026, a projeção do grafo foi integrada à aplicação. Um
roteador determinístico separa perguntas semânticas, estruturais e híbridas.
Contagens e rankings são calculados por SQL, sem estimativa da LLM; perguntas
híbridas usam o grafo para restringir os documentos antes da busca vetorial.
Cada decisão é registrada em `query_route_runs`, com versão, intenção,
parâmetros, consulta, duração e vínculo com a recuperação. A validação confirmou
7.628 entidades, 15.717 relações e doze testes unitários aprovados.

## Por que começar pelo banco

O RAG separa conhecimento externo e modelo gerador. Os fragmentos dos trabalhos
serão representados por vetores e armazenados com sua proveniência. O pgvector
permite manter vetores e metadados no mesmo banco transacional, reduzindo a
complexidade operacional e facilitando a reprodução dos experimentos.

Nesta primeira versão, a recuperação será exclusivamente semântica. Não haverá
comparação com busca lexical. A qualidade será avaliada por relevância dos
trechos recuperados, fidelidade das respostas às evidências, validade das
citações e capacidade de recusar perguntas sem suporte no corpus.

## Arquivos desta etapa

- `compose.yaml`: descreve o serviço PostgreSQL/pgvector.
- `.env.example`: modelo das credenciais locais; a senha real não será versionada.
- `sql/001_pgvector.sql`: habilita a extensão vetorial.
- `sql/003_corpus_schema.sql`: cria as tabelas de documentos e páginas.
- `src/rag_anais/extract_sample.py`: extrai e mede a amostra textual.
- `src/rag_anais/extract_corpus.py`: realiza a extração integral em lotes retomáveis.
- `logs/corpus_extraction.log`: registra o progresso da execução integral.
- `sql/005_chunks_schema.sql`: cria a tabela de fragmentos com proveniência.
- `src/rag_anais/segment_sample.py`: segmenta e mede a amostra aprovada.
- `logs/sample_segmentation.log`: registra a segmentação da amostra.
- `src/rag_anais/segment_corpus.py`: segmenta integralmente o corpus em lotes retomáveis.
- `logs/corpus_segmentation.log`: registra o progresso da segmentação integral.
- `requirements-embeddings.txt`: fixa as dependências diretas da vetorização.
- `src/rag_anais/audit_embedding_tokens.py`: mede os fragmentos com o tokenizer real.
- `src/rag_anais/generate_sample_embeddings.py`: gera a amostra vetorial estratificada.
- `logs/sample_embeddings.log`: registra carregamento e inferência da amostra.
- `src/rag_anais/generate_corpus_embeddings.py`: gera todos os vetores com checkpoints.
- `logs/corpus_embeddings.log`: registra a vetorização integral.
- `src/rag_anais/web_app.py`: API local de busca, histórico, métricas e julgamentos.
- `web/static/`: interface responsiva utilizada pelo avaliador.
- `sql/011_retrieval_evaluation_schema.sql`: tabelas de consultas, rankings e relevância.
- `sql/012_generated_answers_schema.sql`: respostas do LLM e fontes fornecidas ao modelo.
- `scripts/start_web.ps1`: inicia a interface em `http://127.0.0.1:8765`.
- `logs/web_interface.log`: registra buscas, tempos e avaliações realizadas.
- `src/rag_anais/graph_queries.py`: classifica perguntas e executa consultas do grafo.
- `sql/016_query_routing_schema.sql`: registra decisões e resultados do roteamento.
- `scripts/validate_graph_query_integration.py`: valida as rotas estrutural e híbrida.
- `output/pdf/relatorio_integracao_grafo_rag.pdf`: memorial científico da integração.
- `docs/ETAPAS.md`: protocolo incremental de desenvolvimento e validação.
- `docs/DESENVOLVIMENTO_ASSISTIDO_POR_IA.md`: regras de transparência do uso de IA.

## Como validar a configuração

```powershell
Copy-Item .env.example .env
docker compose config
docker compose up -d postgres
Get-Content sql/002_validacao_pgvector.sql -Raw | docker compose exec -T postgres psql -X -v ON_ERROR_STOP=1 -U rag_user -d rag_anais
```

As evidências consolidadas estão em `artifacts/validacao_banco_2026-11-11.json`.

## Como usar a interface de avaliação

Com o Docker Desktop e o Ollama em execução, confirme que o modelo está instalado
e inicie os serviços:

```powershell
ollama list
docker compose up -d postgres
.\scripts\start_web.ps1
```

Abra `http://127.0.0.1:8765`. A primeira consulta carrega o modelo local e tende
a levar mais tempo; as consultas seguintes reutilizam o modelo em memória. O
arquivo `logs/web_interface.log` permite acompanhar as operações sem consultar
diretamente o banco. A configuração reproduzível atual usa `llama3:latest`,
temperatura zero, semente 42, contexto de 8.192 tokens e até 700 tokens de saída.

## Base científica

O conceito de RAG adotado é o de combinar recuperação de memória externa com
um modelo gerador, conforme Lewis et al. (2020). O pgvector oferece busca exata
por padrão e índices aproximados HNSW/IVFFlat; a decisão entre busca exata e HNSW
será tomada depois de medir quantidade de fragmentos, latência e recall.

Referências:

- Lewis, P. et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS, 2020.
- pgvector. Open-source vector similarity search for PostgreSQL. Documentação oficial.

