# Protocolo de desenvolvimento por etapas

Cada etapa produz um resultado observável, um teste e um registro metodológico.
A etapa seguinte somente começa depois da revisão humana da anterior.

## Etapa 1 - ambiente e pgvector (concluída em 11/11/2026)

Objetivo: criar um PostgreSQL isolado e reproduzível com a extensão pgvector.

Critérios de aceite verificados:

1. `docker compose config` não apresentou erro;
2. a imagem `pgvector/pgvector:0.8.7-pg17` está fixada por versão e teve seu digest registrado;
3. a configuração real permanece fora do controle de versão;
4. o banco usa o volume persistente `postgres_data`;
5. a consulta à extensão confirmou pgvector 0.8.7;
6. distâncias de cosseno e euclidiana coincidiram com os valores esperados;
7. três vetores permaneceram disponíveis após reiniciar o contêiner;
8. o serviço ficou saudável e acessível apenas em `127.0.0.1:25432`.

## Etapa 2 - auditoria do corpus (concluída em 11/11/2026)

O programa somente de leitura conferiu manifesto, presença dos PDFs, tamanho,
assinatura `%PDF`, abertura estrutural, páginas, hash SHA-256, duplicatas e
distribuição por edição. Foram auditados 3.969 PDFs e 3.970 páginas, sem arquivos
ausentes, duplicatas por conteúdo ou erros críticos. O corpus foi liberado para
a etapa de extração textual.

## Etapa 3 - extração de texto (concluída em 12/11/2026)

Extração página a página, preservando número da página e arquivo de origem.
Serão calculadas métricas de qualidade para separar documentos que exigem OCR.

Após a aprovação humana da amostra determinística, a execução integral processou
3.969 documentos e 3.970 páginas em 16 lotes. Todas as páginas produziram texto,
sem erros, páginas vazias ou candidatos automáticos a OCR. A validação no banco
confirmou as contagens, a proveniência, as sequências de páginas e os hashes. O
corpus textual foi liberado para a etapa de segmentação.

## Etapa 4 - segmentação (concluída em 12/11/2026)

Os textos serão divididos em fragmentos com tamanho e sobreposição registrados.
Uma amostra será inspecionada manualmente antes de processar todo o corpus.

Após a aprovação da amostra, as 3.970 páginas foram processadas em 16 lotes e
produziram 7.276 fragmentos. O método preserva sentenças quando possível, usa
alvo de 450 unidades lexicais e sobreposição planejada de 75 unidades. Não foram
encontrados caracteres úteis sem cobertura, identificadores duplicados,
fragmentos órfãos ou divergências com o texto de origem. O corpus segmentado foi
liberado para a seleção do modelo de embeddings.

## Etapa 5 - embeddings e pgvector (concluída em 12/11/2026)

Será selecionado um modelo multilíngue adequado ao português. Nome, revisão,
dimensão e parâmetros serão fixados. Os vetores serão ligados ao fragmento,
página, documento e edição que os originaram.

Estado atual: foi selecionado o BAAI/bge-m3, fixado pela revisão
`5617a9f61b028005a4858fdac845db406aefb181`. A auditoria com o tokenizer real
confirmou que os 7.276 fragmentos cabem no limite configurado de 1.024 tokens.
Uma amostra determinística de 25 fragmentos, cinco por edição, produziu vetores
normalizados de 1.024 dimensões e foi validada no pgvector sem truncamento. A
qualidade técnica da configuração. Após essa validação, os 7.276 fragmentos
foram vetorizados e armazenados no pgvector. Todos possuem 1.024 dimensões,
nenhum foi truncado e nenhum fragmento ficou sem embedding. A qualidade
semântica será verificada na etapa de recuperação com julgamento humano.

## Etapa 6 - recuperação semântica (implementação concluída em 13/11/2026)

A consulta será vetorizada pelo mesmo modelo. O pgvector calculará a distância
de cosseno e retornará os fragmentos mais próximos. Inicialmente será usada busca
exata; HNSW só será adotado se os testes demonstrarem necessidade e recall aceitável.

Foi criada uma interface web local para formular perguntas, selecionar `top_k`,
inspecionar fragmentos e PDFs de origem e classificar cada resultado como relevante,
parcialmente relevante ou não relevante. Consultas, rankings, distâncias, tempos e
julgamentos são persistidos no PostgreSQL. A validação funcional confirmou busca,
registro, histórico e métricas; os dados sintéticos foram removidos antes do início
da coleta humana. A próxima atividade desta etapa é definir e congelar o protocolo
de perguntas e julgamentos.

## Etapa 7 - geração fundamentada (linha de base concluída em 13/11/2026)

O modelo receberá apenas a pergunta e os trechos recuperados. O prompt exigirá
citações, proibição de conhecimento externo e resposta de insuficiência quando
as evidências não sustentarem uma conclusão.

Foi integrada uma linha de base com Ollama 0.40.16 e `llama3:latest`, fixado pelo
digest `365c0bd3c000a25d28ddbf732fe1c6add414de7275464c4e4d1c3b5fcb5d8ad1`.
O sistema recupera cinco fragmentos por distância de cosseno, remove repetições
do mesmo documento no contexto e gera a resposta localmente com temperatura 0,
semente 42, contexto de 8.192 tokens e limite de 700 tokens de saída. Resposta,
parâmetros, tempos e fontes são persistidos no PostgreSQL. A interface apresenta
a resposta, as fontes numeradas e os fragmentos recuperados.

Após ser observado que o LLM confundiu autores citados no corpo de um resumo com
a autoria do trabalho, a versão `rag-baseline-v1.4` passou a obter título e
participante diretamente dos metadados do corpus. A interface acrescenta um
catálogo determinístico antes da síntese do LLM, contendo título, participante,
edição e marcador da fonte. O texto integral da página é utilizado como contexto
e títulos repetidos são removidos. A síntese gerativa continua sujeita a erros de
atribuição e será avaliada e otimizada nas etapas posteriores.

Na versão `rag-baseline-v1.5`, o catálogo também passou a apresentar o orientador
de cada trabalho. O nome é obtido deterministicamente pela correspondência entre
o número do autor no cabeçalho e a afiliação marcada como `Orientador(a)`. A
verificação sobre o corpus identificou automaticamente 3.965 dos 3.969 cabeçalhos
que contêm essa marcação; nos quatro casos sem nome recuperável, a interface
informa que o orientador não foi identificado no cabeçalho, sem tentar inferi-lo.

## Etapa 8 — avaliação do RAG

Um conjunto de perguntas será aprovado por humanos e congelado por versão.
Serão avaliados: Recall@k dos trechos, fidelidade factual, correção das citações,
relevância da resposta, taxa de recusa correta e tempo de resposta.

A linha de base funcional será preservada como referência. As próximas versões
serão comparadas com o mesmo conjunto congelado de perguntas, permitindo mostrar
no TCC como reranqueamento, montagem de contexto, prompts, modelos e, futuramente,
grafos alteram a qualidade das respostas.

