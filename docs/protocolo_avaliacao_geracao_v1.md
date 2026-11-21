# Protocolo de avaliação humana da geração - RAG V1

## Objetivo

Avaliar separadamente a etapa de geração da linha de base do RAG, verificando
se o modelo de linguagem transforma as fontes recuperadas em uma resposta
correta, fundamentada e coerente. Esta avaliação não substitui Recall@5 e MRR,
que medem o recuperador.

## Unidade de avaliação

Cada unidade é composta por uma pergunta, a resposta produzida pelo Ollama com
o modelo `llama3:latest` e as cinco fontes efetivamente fornecidas ao modelo. O
conjunto congelado contém dez respostas geradas com o prompt
`rag-baseline-v1.5`.

## Critérios

Quatro critérios recebem pontuação ordinal de 0 a 2:

1. **Fidelidade às fontes**
   - 0: há contradição ou afirmação central sem apoio nas fontes;
   - 1: a resposta é parcialmente sustentada, mas contém imprecisão ou
     afirmação secundária sem apoio;
   - 2: todas as afirmações factuais verificadas estão apoiadas nas fontes.
2. **Correção das citações**
   - 0: os marcadores apontam sistematicamente para fontes erradas ou estão
     ausentes em afirmações centrais;
   - 1: parte das citações está correta, mas há erro ou omissão localizada;
   - 2: os marcadores `[F#]` identificam corretamente as fontes das afirmações.
3. **Completude**
   - 0: a resposta não atende ao núcleo da pergunta;
   - 1: responde parcialmente ou omite evidências importantes disponíveis;
   - 2: responde ao que foi solicitado usando adequadamente as fontes
     disponíveis.
4. **Separação entre fontes**
   - 0: há transferência clara de autor, objetivo, método ou resultado entre
     trabalhos;
   - 1: há ambiguidade ou mistura menor que não altera o sentido central;
   - 2: cada informação permanece vinculada ao trabalho correto.

A adequação da recusa é registrada separadamente como `não se aplica`,
`adequada` ou `inadequada`. Ela não é somada aos quatro critérios. O campo de
observações deve descrever o erro concreto encontrado, quando houver.

## Análise planejada

Serão apresentadas, para cada critério, a distribuição das pontuações e a média
das dez respostas. Não será calculada uma nota global, pois os critérios medem
propriedades diferentes. Também serão contabilizadas recusas adequadas e
inadequadas e resumidos qualitativamente os erros de citação, omissão,
informação sem suporte e mistura entre fontes.

Como o conjunto possui dez perguntas e um avaliador, os resultados serão
tratados como avaliação humana inicial da linha de base, sem inferência
estatística para outras consultas ou outros avaliadores.

## Reprodutibilidade

- Conjunto: `rag-v1-10-questions`.
- Respostas avaliadas: identificadores 19, 20 e 22 a 29.
- Esquema: `sql/013_generation_evaluation_schema.sql`.
- Constituição do conjunto: `sql/014_seed_generation_evaluation_v1.sql`.
- Interface e API: `src/rag_anais/web_app.py` e `web/static/`.
- Tabela de julgamentos: `answer_generation_judgments`.

## Resultados obtidos

As dez respostas foram avaliadas. Fidelidade às fontes, correção das citações,
completude e separação entre fontes receberam pontuação 2 nas dez unidades;
portanto, cada critério apresentou média 2,00, mínimo 2 e máximo 2. Nove
respostas foram classificadas como casos em que a recusa não se aplicava. Na
pergunta 8, sobre soluções de inovação tecnológica desenvolvidas na UESC, a
recusa foi considerada adequada. Não houve recusa inadequada.

Esses resultados indicam que, para o conjunto avaliado e segundo o julgamento
do avaliador, a etapa geradora utilizou corretamente as evidências recuperadas.
Eles não demonstram desempenho perfeito para perguntas não avaliadas. O tamanho
reduzido da amostra e a participação de um único avaliador impedem medir a
concordância entre avaliadores e limitam a generalização.

Os resultados auditáveis estão em
`artifacts/human_evaluation/generation_evaluation_v1_results.json` e
`artifacts/human_evaluation/generation_evaluation_v1_results.csv`. O programa
`scripts/summarize_generation_evaluation.py` recalcula os agregados diretamente
dos registros do PostgreSQL.

