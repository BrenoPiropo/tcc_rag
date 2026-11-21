# Experimento para a versão 2 do recuperador

## Objetivo

Avaliar se o reranqueamento por *Maximal Marginal Relevance* (MMR) melhora a
seleção das cinco evidências apresentadas ao gerador, sem modificar o corpus, a
segmentação, os embeddings, a busca vetorial nem os julgamentos humanos da
versão 1.

## Configuração controlada

- Recuperação inicial: 20 fragmentos pela distância de cosseno no pgvector.
- Reranqueamento: MMR.
- Fragmentos finais: 5.
- Parâmetro de equilíbrio: lambda igual a 0,70.
- Consultas: as mesmas 10 perguntas da avaliação humana da versão 1.
- Referência de relevância: 200 julgamentos humanos, correspondentes aos 20
  primeiros resultados de cada pergunta.
- Métricas principais: Recall@5 relativo ao conjunto julgado e MRR.
- Medida auxiliar: número médio de documentos distintos nos cinco resultados.

O MMR atribui a cada candidato uma pontuação que combina a similaridade entre a
pergunta e o fragmento com uma penalização pela semelhança em relação aos
fragmentos já selecionados. Com lambda igual a 0,70, a relevância semântica
recebe peso de 70% e a penalização de redundância recebe peso de 30%.

## Resultado

| Medida | Versão 1 | MMR (lambda = 0,70) |
|---|---:|---:|
| Recall@5 macro relativo ao pool@20 | 0,3504 | 0,2369 |
| MRR | 1,0000 | 1,0000 |
| Documentos distintos médios em cinco resultados | 4,8 | 5,0 |

## Interpretação

O MMR aumentou discretamente a diversidade documental, mas reduziu o Recall@5.
O MRR permaneceu igual porque o primeiro resultado relevante continuou na
primeira posição em todas as perguntas. Assim, a configuração com lambda igual
a 0,70 não será adotada como versão 2 definitiva. O ensaio demonstra que o
aumento de diversidade, isoladamente, não garante maior cobertura de evidências
relevantes neste corpus.

O resultado é retrospectivo e restrito ao conjunto de 20 candidatos julgados em
cada pergunta. Ele não representa o recall exaustivo de todo o corpus. A próxima
alternativa será um reranqueador semântico do tipo *cross-encoder*, avaliado sob
o mesmo protocolo e comparado diretamente com a versão 1.

## Segundo ensaio: cross-encoder multilíngue

Foi avaliado o modelo `BAAI/bge-reranker-v2-m3`, na revisão imutável
`953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`. O modelo recebeu diretamente
cada par formado pela pergunta e por um dos 20 fragmentos recuperados pela busca
vetorial. A pontuação produzida foi usada para reordenar os candidatos, dos quais
os cinco primeiros foram avaliados.

O corpus, os fragmentos, os embeddings, a recuperação inicial e os julgamentos
humanos permaneceram inalterados. Essa decisão isola o efeito do reranqueador.

| Medida | Versão 1 | Cross-encoder |
|---|---:|---:|
| Recall@5 macro relativo ao pool@20 | 0,3504 | 0,2696 |
| MRR | 1,0000 | 0,9500 |
| Documentos distintos médios em cinco resultados | 4,8 | 4,9 |

O cross-encoder isolado não superou a versão 1. Embora tenha aumentado
discretamente a diversidade documental, reduziu tanto a cobertura das evidências
relevantes quanto a posição do primeiro resultado relevante em uma das consultas.

## Terceiro ensaio: fusão de pontuações

Também foi testada uma combinação linear entre a similaridade densa e a
pontuação do cross-encoder. As duas pontuações foram normalizadas por pergunta
com o método mínimo-máximo. O peso `alpha` foi aplicado à similaridade densa e o
peso `1 - alpha` à pontuação do cross-encoder.

Para reduzir o risco de escolher um parâmetro com base nas mesmas consultas
usadas na comparação, as perguntas 1 a 5 foram utilizadas para desenvolvimento e
as perguntas 6 a 10 foram mantidas como conjunto de teste. Foram avaliados os
valores 0,00; 0,25; 0,50; 0,75; 0,90 e 1,00. O melhor resultado no conjunto de
desenvolvimento ocorreu com `alpha = 1,00`, que equivale a preservar somente a
ordenação vetorial original. No conjunto de teste, a V1 e essa configuração
obtiveram Recall@5 de 0,3217 e MRR de 1,0000.

Portanto, os dados disponíveis não justificam substituir o recuperador da versão
1 pelo MMR, pelo cross-encoder isolado ou pela fusão avaliada. Esses resultados
negativos são preservados porque delimitam empiricamente quais modificações não
melhoraram o sistema e evitam a adoção de uma versão com desempenho inferior.

## Reprodutibilidade

- Implementação do MMR: `src/rag_anais/reranking.py`.
- Testes automatizados: `tests/test_reranking.py`.
- Avaliação: `scripts/evaluate_retriever_v2.py`.
- Resultado detalhado: `artifacts/human_evaluation/retriever_v2_mmr_evaluation.json`.
- Implementação do cross-encoder: `src/rag_anais/cross_encoder_reranking.py`.
- Download reproduzível: `scripts/download_reranker_v2.py`.
- Avaliação do cross-encoder: `scripts/evaluate_retriever_v2_cross_encoder.py`.
- Resultado do cross-encoder:
  `artifacts/human_evaluation/retriever_v2_cross_encoder_evaluation.json`.
- Avaliação da fusão: `scripts/evaluate_retriever_v2_fusion.py`.
- Resultado da fusão:
  `artifacts/human_evaluation/retriever_v2_fusion_evaluation.json`.

