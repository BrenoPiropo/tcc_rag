# Implementação da projeção do grafo de conhecimento

## Finalidade

A projeção do grafo foi criada para responder perguntas estruturais que não são
adequadamente resolvidas pela recuperação de fragmentos, como quantificar os
trabalhos orientados por uma pessoa, relacionar trabalhos às edições e cursos ou
percorrer vínculos entre essas entidades. A recuperação semântica continua sendo
utilizada para perguntas sobre o conteúdo textual. O grafo complementa o RAG e
não substitui os embeddings nem o pgvector.

## Decisão arquitetural

O grafo foi persistido no PostgreSQL já utilizado pelo projeto, no modelo de
grafo de propriedades. Essa decisão mantém os dados textuais, vetoriais,
relacionais e estruturais sob as mesmas transações e restrições de integridade,
evitando introduzir um segundo servidor nesta fase do TCC. A representação pode
ser exportada posteriormente para um mecanismo de grafos sem modificar o
processo de extração.

O modelo utiliza duas tabelas novas:

- `knowledge_graph_entities`: armazena os nós e seus atributos;
- `knowledge_graph_relations`: armazena as arestas direcionadas e a proveniência
  documental de cada relação.

A tabela preexistente `documents` permanece como a fonte de proveniência. Cada
aresta aponta para o SHA-256 do PDF e para a página da qual o vínculo foi
extraído. A Figura `der_grafo_conhecimento.png` representa o DER implementado.

## Tipos de nós e relações

Foram definidos quatro tipos de nó:

- `work`: um trabalho publicado nos Anais, identificado pelo SHA-256 do PDF;
- `person`: participante principal ou orientador, consolidado por nome
  normalizado;
- `edition`: uma das edições 1 a 5;
- `course`: curso informado no cabeçalho do trabalho.

As arestas partem do nó `work`:

- `AUTHORED_BY`: liga o trabalho ao participante principal;
- `ADVISED_BY`: liga o trabalho ao orientador;
- `PRESENTED_IN`: liga o trabalho à edição;
- `ASSOCIATED_WITH_COURSE`: liga o trabalho ao curso.

## Extração dos metadados

O arquivo `src/rag_anais/graph_metadata.py` contém o extrator determinístico. O
programa utiliza o texto da primeira página, já armazenado na tabela `pages`, e
executa as seguintes operações:

1. localiza a linha do participante principal a partir do metadado do portal;
2. considera como título as linhas situadas entre o código do trabalho e o bloco
   de autoria;
3. lê o curso no campo `CURSO:` do cabeçalho;
4. associa os números sobrescritos do bloco de autores às afiliações;
5. identifica como orientador o nome cujo número está vinculado ao marcador
   `Orientador(a)`;
6. registra avisos quando título, curso ou orientador não podem ser obtidos.

O orientador não é inferido pela LLM. A relação é criada somente quando o
marcador explícito existe no cabeçalho. Dados ausentes permanecem ausentes para
evitar a fabricação de vínculos.

## Normalização e identificadores

Nomes e cursos são normalizados para reduzir duplicações produzidas por
diferenças de caixa, acentuação e espaços. A forma normalizada é convertida em
uma chave canônica. O rótulo original permanece armazenado para apresentação.

Os identificadores de nós são hashes SHA-256 determinísticos da combinação
entre o tipo da entidade e sua chave canônica. Os identificadores das relações
também são hashes determinísticos da origem, tipo, destino e documento de
proveniência. Assim, uma nova execução com as mesmas entradas produz os mesmos
identificadores e pode atualizar o banco de forma idempotente.

A consolidação de pessoas pelo nome normalizado possui uma limitação: homônimos
podem ser representados como uma única pessoa. O relatório registra essa
restrição e preserva a proveniência necessária para futura desambiguação.

## Auditoria anterior à carga

Antes da execução integral, uma amostra estratificada de 20 documentos, formada
por quatro registros de cada edição, foi analisada. Título, orientador e curso
foram identificados nos 20 documentos. O resultado está em
`artifacts/knowledge_graph/metadata_sample.csv` e
`metadata_sample_summary.json`.

Em seguida, o programa `scripts/build_knowledge_graph.py` foi executado sem a
opção de escrita. Essa prévia processou os 3.969 documentos e calculou a
cobertura antes de qualquer alteração no banco:

| Metadado | Documentos identificados | Cobertura |
|---|---:|---:|
| Título | 3.969 | 100,00% |
| Orientador | 3.965 | 99,90% |
| Curso | 3.814 | 96,09% |

Quatro documentos não apresentaram orientador identificável e 155 não
apresentaram curso no formato reconhecido. Esses registros foram mantidos com
relações parciais e incluídos no arquivo
`artifacts/knowledge_graph/knowledge_graph_warnings.csv`.

## Carga integral

Após a validação da cobertura, o mesmo programa foi executado com a opção
`--write`. Todos os nós e relações foram gravados em uma única transação. Uma
falha antes do commit reverte integralmente a carga, impedindo um grafo
parcialmente persistido. A versão do extrator, `graph-metadata-v1`, acompanha
cada registro.

A carga produziu 7.628 nós:

| Tipo de nó | Quantidade |
|---|---:|
| Trabalho | 3.969 |
| Pessoa | 3.594 |
| Curso | 60 |
| Edição | 5 |

Foram criadas 15.717 relações:

| Tipo de relação | Quantidade |
|---|---:|
| `AUTHORED_BY` | 3.969 |
| `ADVISED_BY` | 3.965 |
| `PRESENTED_IN` | 3.969 |
| `ASSOCIATED_WITH_COURSE` | 3.814 |

## Validação

O programa `scripts/validate_knowledge_graph.py` verificou que:

- os 3.969 documentos possuem um nó de trabalho correspondente;
- não existem relações órfãs;
- cada trabalho possui exatamente uma relação `AUTHORED_BY`;
- cada trabalho possui exatamente uma relação `PRESENTED_IN`;
- as quantidades por edição são 680, 973, 733, 754 e 829, iguais às contagens
  auditadas do corpus.

O resultado completo foi salvo em
`artifacts/knowledge_graph/knowledge_graph_validation.json`.

## Exemplo de consulta estrutural

A pergunta "qual orientador possui mais trabalhos?" é respondida por uma
agregação das arestas `ADVISED_BY`, contando documentos distintos por nó de
pessoa. Na carga atual, o primeiro resultado é Wolney Gomes Almeida, com 47
trabalhos. Esse resultado deve ser apresentado com a ressalva de que a identidade
é consolidada por nome normalizado e ainda necessita de revisão de homônimos.

O ranking foi preservado em
`artifacts/knowledge_graph/top_advisors_by_work_count.csv`.
A visão SQL `knowledge_graph_advisor_work_counts` materializa a lógica da
contagem para que a aplicação possa reutilizá-la sem duplicar a consulta.

## Arquivos de reprodutibilidade

- `sql/015_knowledge_graph_schema.sql`: cria as tabelas, restrições e índices;
- `scripts/apply_knowledge_graph_schema.py`: aplica e valida o esquema;
- `src/rag_anais/graph_metadata.py`: extrai e normaliza os metadados;
- `tests/test_graph_metadata.py`: testa extração e identificadores;
- `scripts/audit_knowledge_graph_metadata_sample.py`: audita a amostra;
- `scripts/build_knowledge_graph.py`: gera a prévia e executa a carga integral;
- `scripts/validate_knowledge_graph.py`: verifica integridade e consultas;
- `scripts/generate_knowledge_graph_der.py`: reproduz a imagem do DER;
- `logs/knowledge_graph_build.log`: registra o processamento integral.

## Etapa seguinte

A próxima etapa é integrar consultas determinísticas do grafo à interface. Um
classificador de intenção deverá separar perguntas textuais, encaminhadas ao RAG
vetorial, de perguntas estruturais, encaminhadas ao grafo. A resposta deverá
informar o caminho consultado e preservar os PDFs que sustentam cada relação.

