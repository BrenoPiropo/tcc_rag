# Memorial científico do desenvolvimento do RAG dos Anais da SIC/UESC

Versão 0.12 - 13 de novembro de 2026

Status: documento em construção

## Resumo

Este memorial registra, de forma progressiva e verificável, o desenvolvimento de um sistema de geração aumentada por recuperação, ou Retrieval-Augmented Generation (RAG), aplicado aos Anais da Semana de Iniciação Científica da Universidade Estadual de Santa Cruz (UESC). O corpus compreende os documentos das edições 1 a 5 disponíveis na base local. A auditoria automatizada confirmou 3.969 PDFs e 3.970 páginas. O sistema utiliza recuperação semântica com embeddings armazenados em PostgreSQL por meio da extensão pgvector. A construção é realizada com assistência de inteligência artificial, sob revisão humana e com registro das decisões, testes e evidências produzidas. Nesta versão são documentadas as validações concluídas da infraestrutura vetorial, do corpus, da extração textual integral, da segmentação integral, da vetorização integral, da interface de avaliação e de uma linha de base completa que utiliza um modelo de linguagem local para produzir respostas fundamentadas. A otimização e a avaliação sistemática do RAG ainda serão executadas.

Palavras-chave: recuperação aumentada por geração; RAG; pgvector; embeddings; literatura científica; iniciação científica.

## 1 Introdução

Modelos de linguagem podem produzir respostas linguisticamente plausíveis sem que suas afirmações estejam sustentadas por uma fonte documental específica. A arquitetura RAG busca reduzir esse problema ao recuperar evidências de uma coleção externa e fornecê-las ao modelo gerador durante a elaboração da resposta. Dessa forma, o conhecimento utilizado não depende apenas dos parâmetros internos do modelo, mas também de uma memória documental explicitamente consultada.

Neste trabalho, a memória externa será composta pelos Anais da Semana de Iniciação Científica da UESC. O objetivo técnico é permitir perguntas em linguagem natural e produzir respostas fundamentadas nos documentos recuperados, acompanhadas da identificação das fontes utilizadas. O objetivo científico é construir e avaliar esse processo de maneira reproduzível, registrando as decisões de preparação do corpus, representação vetorial, recuperação, geração e avaliação.

## 2 Delimitação do sistema

O projeto considera exclusivamente os Anais da SIC/UESC das edições 1 a 5 disponíveis no corpus local. A recuperação será semântica, baseada na proximidade entre o vetor da pergunta e os vetores dos fragmentos documentais. Não faz parte do escopo realizar uma comparação experimental com mecanismos de busca lexical.

O sistema deverá:

- preservar a ligação entre cada fragmento, sua página, seu documento e sua edição;
- recuperar trechos semanticamente relacionados à pergunta;
- responder apenas com base nas evidências recuperadas;
- apresentar citações rastreáveis;
- informar insuficiência de evidência quando o corpus não sustentar uma resposta;
- registrar configurações, versões, tempos e resultados de cada execução.

## 3 Fundamentação da arquitetura RAG

Lewis et al. (2020) descrevem RAG como uma arquitetura que combina memória paramétrica, representada pelo modelo de linguagem, e memória não paramétrica, representada por uma coleção documental recuperável. No presente projeto, os fragmentos dos anais constituirão a memória não paramétrica.

Cada fragmento será transformado em um embedding, isto é, um vetor numérico que representa características semânticas do texto. A pergunta será convertida pelo mesmo modelo de embeddings. A recuperação será realizada pela distância de cosseno no espaço vetorial. Quanto menor a distância entre dois vetores, maior tende a ser sua proximidade semântica segundo o modelo utilizado.

Os embeddings e seus metadados serão armazenados no PostgreSQL com a extensão pgvector. Essa escolha mantém representação vetorial, proveniência e dados de execução no mesmo sistema gerenciador. O pgvector oferece busca exata e índices aproximados. A busca exata será adotada inicialmente como referência, pois não introduz perda de recall decorrente da aproximação. A adoção futura de HNSW dependerá da quantidade observada de fragmentos e de medições de latência e recall.

## 4 Método incremental e critérios de evidência

O desenvolvimento foi dividido em etapas para que cada componente possa ser verificado antes da introdução do componente seguinte. Para cada etapa serão registrados objetivo, entradas, procedimento, configuração, saída, teste, resultado e limitações.

As etapas previstas são:

1. preparação e validação do PostgreSQL com pgvector;
2. auditoria do corpus de PDFs;
3. extração de texto página a página;
4. segmentação dos textos em fragmentos;
5. seleção e aplicação do modelo de embeddings;
6. armazenamento e recuperação semântica com pgvector;
7. geração de respostas fundamentadas;
8. avaliação da recuperação e das respostas.

Uma etapa somente será considerada concluída quando houver uma evidência reproduzível. Exemplos de evidência incluem resultado de consulta SQL, hash de arquivo, relatório de auditoria, teste automatizado, métrica calculada ou inspeção humana registrada.

## 5 Desenvolvimento assistido por inteligência artificial

A inteligência artificial é utilizada como ferramenta de apoio à arquitetura, elaboração de rascunhos de código, produção de testes, documentação e análise de erros. O emprego dessa ferramenta não transfere a responsabilidade científica para o sistema de IA.

As decisões sobre o problema, o corpus, os critérios de sucesso, a relevância dos documentos e a interpretação dos resultados permanecem sob responsabilidade humana. Código e texto sugeridos por IA somente serão aceitos após inspeção e apresentação de evidência verificável.

Para cada alteração relevante serão registrados:

- data e objetivo da intervenção;
- ferramenta ou modelo de IA utilizado;
- artefato produzido ou modificado;
- revisão humana realizada;
- correções efetuadas;
- evidência usada para aceitar a alteração.

## 6 Etapa 1 - preparação do banco vetorial

### 6.1 Objetivo

O objetivo da primeira etapa é disponibilizar uma instância isolada e reproduzível do PostgreSQL com a extensão pgvector. Nenhum PDF é processado nesta etapa.

### 6.2 Organização inicial do projeto

Foi criado um projeto independente denominado `rag_anais_uesc`. A estrutura inicial contém um arquivo de orquestração do Docker, um modelo de variáveis de ambiente, um script SQL para habilitar o pgvector e documentação do protocolo de desenvolvimento.

O arquivo `compose.yaml` fixa a imagem `pgvector/pgvector:0.8.7-pg17`, correspondente ao PostgreSQL 17 com pgvector 0.8.7. A fixação explícita das versões reduz variações entre execuções e favorece a reprodução do ambiente.

O PostgreSQL utiliza a porta 5432 dentro do contêiner e é exposto exclusivamente no endereço local `127.0.0.1`, pela porta 25432 do computador. As portas inicialmente avaliadas, 5433 e 5434, estavam indisponíveis no ambiente. Antes da alteração definitiva, a possibilidade de associação à porta 25432 foi testada localmente. Essa escolha evitou interferir em serviços e reservas existentes. A restrição ao endereço local impede a exposição direta do banco à rede. Os dados serão mantidos no volume persistente `postgres_data`, permitindo encerrar e recriar o contêiner sem apagar o banco.

O script `sql/001_pgvector.sql` contém a instrução:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Essa instrução habilita os tipos e operadores vetoriais fornecidos pelo pgvector. O modificador `IF NOT EXISTS` permite repetir a inicialização sem tentar recriar uma extensão já instalada.

### 6.3 Segurança das configurações

O arquivo `.env.example` contém apenas valores de exemplo. A senha real será armazenada em um arquivo `.env`, excluído do controle de versão pelo `.gitignore`. Essa separação evita a publicação acidental de credenciais e preserva um modelo reproduzível das variáveis exigidas.

### 6.4 Validação estrutural e inicialização

Foi executada a validação estrutural `docker compose config --quiet`, concluída sem erro. Essa evidência confirmou que a sintaxe e as relações declaradas no arquivo de composição eram reconhecidas pelo Docker Compose.

Na primeira tentativa de inicialização, a porta local 5433 estava indisponível. A porta 5434 apresentou a mesma restrição. Nenhum processo existente foi encerrado. Foram testadas outras possibilidades de associação local e a porta 25432 foi confirmada como disponível. A configuração foi alterada para `127.0.0.1:25432`, preservando a porta interna 5432. O contêiner foi então iniciado e atingiu o estado `healthy`.

### 6.5 Procedimento de validação vetorial

O teste foi definido no script `sql/002_validacao_pgvector.sql`. Foi criada uma tabela de validação com uma coluna `vector(3)`. Três vetores conhecidos foram inseridos:

- vetor A = [1, 0, 0];
- vetor B = [0, 1, 0];
- vetor C = [1, 1, 0].
O vetor A foi usado como referência. Pela definição da distância de cosseno, esperava-se distância 0 para A, aproximadamente 0,292893 para C e 1 para B. Pela distância euclidiana, esperava-se 0 para A, 1 para C e aproximadamente 1,414214 para B.
### 6.6 Resultados observados
O servidor reportou PostgreSQL 17.11, com a distribuição Debian 17.11-1.pgdg12+2. A consulta à tabela `pg_extension` confirmou pgvector 0.8.7. Os três registros apresentaram dimensão 3.

As distâncias observadas foram:

- A: distância de cosseno 0,000000 e distância euclidiana 0,000000;
- C: distância de cosseno 0,292893 e distância euclidiana 1,000000;
- B: distância de cosseno 1,000000 e distância euclidiana 1,414214.

Os valores observados coincidiram com os resultados matemáticos esperados. Em seguida, o contêiner foi reiniciado. Após retornar ao estado `healthy`, a tabela ainda continha três registros, com os rótulos A, B e C. Esse resultado confirmou a persistência do volume.

O relatório JSON da validação registra data e horário, versão do Docker, tag e digest da imagem, versões do PostgreSQL e pgvector, endereço local, resultados das distâncias e hashes SHA-256 dos arquivos de configuração e teste. Com base nessas evidências, a Etapa 1 foi considerada concluída em 11 de novembro de 2026.

## 7 Etapa 2 - auditoria do corpus

### 7.1 Objetivo e procedimento

A segunda etapa teve como objetivo estabelecer o conjunto documental efetivamente disponível antes de qualquer extração de texto ou geração de embeddings. Foi desenvolvido o programa `src/rag_anais/audit_corpus.py`, executado em modo somente leitura sobre o manifesto localizado em `D:/tcc_sic/controle/manifesto.csv`.

Para cada registro foram verificados: edição, identificador do site, status do manifesto, existência do arquivo, correspondência entre tamanho informado e tamanho real, assinatura `%PDF-`, abertura estrutural, presença de criptografia, quantidade de páginas e hash SHA-256. O hash foi calculado em blocos de 1 MiB para limitar o consumo de memória. A abertura estrutural foi realizada com pypdf 6.21.4 em modo não estrito. O programa registrou o progresso a cada 100 documentos e continuou a auditoria mesmo quando uma exceção individual pudesse ocorrer.

Foram produzidos três artefatos: inventário detalhado em CSV, resumo consolidado em JSON e log cronológico. O manifesto utilizado também recebeu um hash SHA-256, permitindo identificar exatamente a entrada da auditoria.

### 7.2 Resultados

A execução iniciou às 19h22min43s e terminou às 19h32min54s de 11 de novembro de 2026, com duração aproximada de 10 minutos e 11 segundos. Foram auditados 3.969 registros, distribuídos da seguinte forma:

- edição 1: 680 documentos;
- edição 2: 973 documentos;
- edição 3: 733 documentos;
- edição 4: 754 documentos;
- edição 5: 829 documentos.

Todos os 3.969 arquivos estavam presentes, possuíam tamanho correspondente ao manifesto, apresentavam assinatura PDF válida e puderam ser abertos estruturalmente. Nenhum documento estava criptografado. O tamanho total observado foi de 845.786.526 bytes.

Foram contabilizadas 3.970 páginas. A quantidade mínima foi uma página e a máxima foi duas páginas; portanto, um único documento possuía duas páginas e os demais possuíam uma página. Não foram encontradas chaves duplicadas no manifesto nem grupos de arquivos com o mesmo SHA-256. O número de registros críticos foi zero.

O hash SHA-256 do manifesto auditado foi `b1fd93e378b2ad89a537baf5b531e2f2dc5ba665d5f569f2b2c939f92c1f76cd`. Com base nesses resultados, o corpus foi considerado apto para a extração textual. Essa conclusão se restringe à integridade física e estrutural dos PDFs; a qualidade do texto extraído ainda deverá ser medida na etapa seguinte.

## 8 Etapa 3 - extração textual

### 8.1 Objetivo e desenho da amostra

A terceira etapa tem como objetivo converter o conteúdo dos PDFs em texto rastreável por página, preservando a ligação com o documento original. Antes do processamento integral, foi definida uma amostra controlada de 20 documentos: quatro por edição, escolhidos de forma determinística em posições distribuídas no inventário ordenado pelo identificador do site. O único documento com duas páginas foi incluído deliberadamente. Esse desenho não pretende estimar estatisticamente a qualidade de todo o corpus; sua finalidade é verificar o funcionamento do procedimento e detectar falhas evidentes antes de ampliar a execução.

### 8.2 Estrutura de dados e proveniência

O script `sql/003_corpus_schema.sql` criou as tabelas `documents` e `pages`. A tabela de documentos utiliza o SHA-256 do PDF como chave primária e registra edição, identificador do site, participante, caminho de origem, tamanho, número de páginas, estado no manifesto e instante da auditoria. A tabela de páginas utiliza a combinação entre o hash do documento e o número da página, mantém chave estrangeira para o documento e armazena texto bruto, texto normalizado, métricas, método, versão do extrator, hash do texto e indicação de necessidade de OCR. Essa modelagem evita que o texto seja separado de sua origem e permite auditar transformações posteriores.

### 8.3 Procedimento de extração e normalização

O programa `src/rag_anais/extract_sample.py` utilizou pypdf 6.21.4, em modo de extração `layout`. O texto de cada página foi normalizado em Unicode NFC; caracteres nulos foram removidos; terminações de linha foram uniformizadas; sequências de espaços e tabulações foram reduzidas; e blocos com mais de duas linhas vazias foram compactados. O texto bruto foi preservado separadamente. Para cada texto normalizado foi calculado um SHA-256, possibilitando verificar sua integridade.

Foram calculados o número total de caracteres, o número de caracteres alfabéticos, a proporção de caracteres alfabéticos e a quantidade de caracteres de substituição Unicode. Uma página é marcada como candidata a OCR quando possui menos de 100 caracteres, proporção alfabética inferior a 0,30 ou ao menos um caractere de substituição. Esses limiares são regras operacionais iniciais e não demonstram, isoladamente, correção semântica; por isso, a inspeção humana permanece obrigatória antes do processamento integral.

### 8.4 Resultados da amostra

A execução ocorreu em 11 de novembro de 2026. Foram processados 20 documentos e 21 páginas. Todas as páginas produziram texto; não houve página vazia nem erro de extração. Nenhuma página atingiu os critérios automáticos para OCR. O conjunto resultou em 63.361 caracteres normalizados. Por página, foram observados mínimo de 1.183 caracteres, máximo de 5.747 e média de 3.017,19 caracteres.

Os 20 documentos e as 21 páginas foram importados no PostgreSQL. A validação confirmou quatro documentos por edição, igualdade entre páginas declaradas e registradas, sequência válida de páginas, ausência de páginas órfãs, formato válido dos hashes e correspondência dos hashes recalculados nos arquivos CSV. Uma inspeção inicial de trechos confirmou a presença de título, autoria, resumo e palavras-chave em português, sem perda textual evidente nos casos observados.

### 8.5 Extração integral

Após a revisão humana e a aprovação da amostra, foi desenvolvido o programa `src/rag_anais/extract_corpus.py`. A execução foi dividida em 16 lotes de até 250 documentos. Cada lote foi gravado de forma independente e atômica, acompanhado de um resumo em JSON. Essa estratégia permite retomar uma execução interrompida reutilizando apenas lotes integralmente concluídos. O progresso foi registrado em `logs/corpus_extraction.log` a cada 100 documentos e ao término de cada lote.

A execução integral ocorreu em 12 de novembro de 2026, entre 12h20min29s e 12h26min06s, no horário local, com duração de 336,703 segundos. Foram processados 3.969 documentos e 3.970 páginas. Todas as páginas produziram texto normalizado: não houve erro de extração, página vazia ou candidato automático a OCR. O corpus textual resultante contém 11.964.293 caracteres normalizados. Por página, o mínimo foi de 1.122 caracteres, o máximo de 5.747 e a média de 3.013,68 caracteres.

### 8.6 Importação e validação no banco

Os arquivos consolidados foram importados nas tabelas `documents` e `pages` por meio de tabelas temporárias e operações idempotentes de inserção ou atualização. A validação confirmou 3.969 documentos, 3.970 páginas e igualdade entre a soma de páginas declaradas e a quantidade de páginas armazenadas. A distribuição por edição permaneceu igual à auditoria: 680 documentos na edição 1, 973 na edição 2, 733 na edição 3, 754 na edição 4 e 829 na edição 5.

Não foram encontradas páginas órfãs, sequências inválidas, chaves duplicadas, hashes textuais malformados ou divergências entre os hashes recalculados e os registrados. Com essas evidências, a Etapa 3 foi considerada concluída e o corpus textual foi liberado para a segmentação.

### 8.7 Limitações

Os critérios automáticos indicam presença e composição mínima do texto, mas não demonstram fidelidade absoluta a elementos visuais, fórmulas, tabelas ou ordem de leitura complexa. A aprovação da amostra reduz esse risco operacional, sem eliminá-lo. A proveniência por documento e página foi preservada para permitir a inspeção de qualquer fragmento nas etapas seguintes. Nenhum embedding foi gerado durante a extração.

## 9 Etapa 4 - segmentação textual

### 9.1 Objetivo e unidade de medida

A segmentação divide o texto de cada página em unidades menores, denominadas fragmentos ou chunks, que posteriormente receberão embeddings. O objetivo é produzir unidades suficientemente específicas para recuperação semântica, mas que preservem contexto bastante para sustentar uma resposta. Fragmentos excessivamente curtos tendem a perder relações argumentativas; fragmentos excessivamente longos podem combinar tópicos distintos e diluir a representação vetorial.

Como o modelo de embeddings ainda não foi selecionado, esta etapa utiliza unidades lexicais Unicode, compostas por palavras e sinais de pontuação, em vez de afirmar contagens do tokenizer de um modelo específico. Essa medida é determinística e independente de fornecedor. Após a seleção do modelo, a quantidade correspondente de tokens do tokenizer será medida e os limites serão confirmados ou ajustados.

### 9.2 Método e parâmetros iniciais

O programa `src/rag_anais/segment_sample.py` opera sobre o texto normalizado e preserva os deslocamentos de caracteres em relação à página. O algoritmo identifica linhas e limites de sentenças, evitando cortar uma sentença quando seu tamanho permite. Sentenças excepcionalmente maiores que o limite são divididas em fronteiras lexicais.

Foram definidos alvo de 450 unidades lexicais, máximo de 520, mínimo desejado de 120 e sobreposição planejada de 75 unidades entre fragmentos consecutivos. Um fragmento final pode ficar abaixo do mínimo para impedir descarte de conteúdo. Esses valores constituem uma configuração inicial sujeita à avaliação da recuperação, e não uma constante universal.

Cada fragmento recebe identificador determinístico SHA-256, número sequencial na página, texto, posições inicial e final, contagem lexical, sobreposição observada, rótulos de seções reconhecidas, hash do texto de origem, hash do fragmento, método e versão da segmentação. A tabela `chunks`, criada pelo script `sql/005_chunks_schema.sql`, mantém chave estrangeira composta para a página de origem. Assim, qualquer fragmento pode ser rastreado até o documento, a edição e a página que o produziram.

### 9.3 Resultados da amostra

Foram segmentados os mesmos 20 documentos e 21 páginas previamente aprovados na extração. O procedimento produziu 37 fragmentos, com mínimo de 116, máximo de 449 e média de 347,89 unidades lexicais. Cada página produziu entre um e quatro fragmentos, com média de 1,76.

A verificação por intervalos confirmou zero caractere não branco sem cobertura. Não houve identificador duplicado. Após a importação no PostgreSQL, a validação confirmou correspondência entre os hashes de origem e das páginas, igualdade entre cada fragmento e o intervalo correspondente do texto normalizado, sequências válidas de fragmentos e formato correto dos hashes.

Para apoiar a inspeção humana, foi produzido o arquivo `artifacts/sample_chunks_review.md`, organizado por edição, participante, documento, página e número do fragmento. Esse artefato apresenta o texto integral de cada chunk, sua contagem lexical, a sobreposição anterior e as seções reconhecidas.

### 9.4 Aprovação da amostra

A inspeção humana aprovou a coerência, o contexto e os limites observados na amostra. Essa decisão autorizou a aplicação dos mesmos parâmetros ao corpus integral, sem alterar o algoritmo ou os limiares entre as duas execuções.

### 9.5 Segmentação integral

O programa `src/rag_anais/segment_corpus.py` processou as 3.970 páginas em 16 lotes de até 250 páginas. Cada lote foi gravado atomicamente e acompanhado por um resumo, permitindo reutilizar lotes concluídos em caso de interrupção. O progresso foi registrado em `logs/corpus_segmentation.log`. A execução ocorreu em 12 de novembro de 2026 e durou 4,641 segundos.

Foram produzidos 7.276 fragmentos para os 3.969 documentos. A distribuição foi de 1.199 fragmentos na edição 1, 1.739 na edição 2, 1.352 na edição 3, 1.414 na edição 4 e 1.572 na edição 5. Os fragmentos apresentaram mínimo de 81, máximo de 450 e média de 335,41 unidades lexicais. Cada página originou entre um e quatro fragmentos, com média de 1,83.

O mínimo de 81 unidades ocorreu em um fragmento final necessário para preservar todo o conteúdo da página. Entre fragmentos não iniciais, a sobreposição variou de 75 a 118 unidades, com média de 82,71. Valores superiores ao alvo de 75 decorrem da preservação de sentenças completas.

### 9.6 Importação, validação e situação

Os 7.276 fragmentos foram sincronizados com a tabela `chunks`. A validação confirmou cobertura de todas as páginas, zero caractere não branco sem cobertura, zero identificador duplicado, zero fragmento órfão, sequências válidas, intervalos dentro dos textos de origem e igualdade entre cada fragmento e o intervalo correspondente da página. Também não houve divergência entre hashes de origem nem fragmento não inicial sem sobreposição.

Com essas evidências, a Etapa 4 foi considerada concluída. O corpus segmentado está liberado para a seleção e avaliação do modelo de embeddings.

O reconhecimento de seções utiliza padrões textuais e não uma análise semântica completa. Além disso, as unidades lexicais provisórias não equivalem necessariamente aos tokens do futuro modelo de embeddings. Essas limitações permanecem registradas para que a configuração seja reavaliada antes da vetorização.

## 10 Etapa 5 - embeddings e pgvector

### 10.1 Seleção e fixação do modelo

Foi selecionado o modelo BAAI/bge-m3, descrito por Chen et al. (2024), por oferecer representação multilíngue, suporte a textos longos e recuperação densa. O modelo produz vetores de 1.024 dimensões e sua arquitetura admite sequências de até 8.192 tokens. Neste projeto será utilizada exclusivamente a saída densa, coerente com a delimitação de recuperação semântica adotada.

A dimensão não foi escolhida isoladamente: ela corresponde à saída nativa para a qual o modelo foi treinado. A coluna vetorial foi, portanto, definida como `vector(1024)`. Essa dimensão está dentro do limite aceito pelo índice HNSW do pgvector e, para 7.276 fragmentos, representa volume compatível com a infraestrutura local.

Para garantir reprodutibilidade, o identificador `BAAI/bge-m3` foi fixado na revisão `5617a9f61b028005a4858fdac845db406aefb181`. O modelo foi armazenado localmente, ocupando 2.293.331.858 bytes no cache. Não foi utilizada API externa para a inferência. O ambiente isolado contém Python 3.12.14, sentence-transformers 6.3.0, transformers 5.22.2, PyTorch 2.15.0 para CPU e NumPy 2.5.4.

### 10.2 Auditoria com o tokenizer do modelo

Antes da inferência, o programa `src/rag_anais/audit_embedding_tokens.py` mediu os 7.276 fragmentos com o tokenizer da revisão fixada. As contagens variaram de 108 a 804 tokens, com média de 475,50, mediana de 564, percentil 95 de 686 e percentil 99 de 720. Foram encontrados 3.930 fragmentos acima de 512 tokens, mas nenhum acima de 1.024.

Esse resultado confirma que um limite de 512 causaria truncamento em parte substancial do corpus. Foi configurado `max_sequence_length` igual a 1.024, suficiente para todos os fragmentos observados e menor que o limite teórico do modelo, reduzindo custo computacional sem perda textual.

### 10.3 Geração da amostra

O programa `src/rag_anais/generate_sample_embeddings.py` selecionou deterministicamente 25 fragmentos distribuídos pelo corpus, cinco de cada edição. Os embeddings foram calculados localmente em CPU, com seis threads, lotes de dois fragmentos e normalização L2. O carregamento inicial do modelo durou 96,984 segundos; a inferência dos 25 fragmentos durou 32,922 segundos; e a execução completa durou 130,172 segundos.

Na amostra, os textos apresentaram entre 142 e 688 tokens do modelo, com média de 494,44. Nenhum texto foi truncado. Todos os vetores possuíam 1.024 componentes. As normas L2 variaram de 0,999999940 a 1,000000119, variação numérica compatível com vetores unitários em ponto flutuante.

### 10.4 Modelagem e validação no pgvector

O script `sql/008_embeddings_schema.sql` criou a tabela `embedding_models`, que registra modelo, revisão, dimensão, limite, normalização, bibliotecas e dispositivo, e a tabela `chunk_embeddings`, que liga cada vetor ao fragmento de origem. A separação permite manter diferentes execuções identificáveis sem remover a proveniência textual.

Os 25 vetores foram importados e distribuídos igualmente entre as cinco edições. A função `vector_dims` confirmou 1.024 dimensões em todos os registros. Não houve vetor truncado ou órfão. As normas recalculadas no PostgreSQL permaneceram entre 0,99999999 e 1,00000012. A distância de cosseno de cada vetor para si mesmo foi zero. Em uma consulta de vizinhança, o próprio fragmento ocupou a primeira posição com distância zero; os dois resultados seguintes apresentaram distâncias 0,34525136 e 0,39611697. Esses testes confirmam armazenamento e operação matemática, mas não substituem a avaliação humana de relevância.

### 10.5 Vetorização integral

Após a validação técnica da amostra, o programa `src/rag_anais/generate_corpus_embeddings.py` processou os 7.276 fragmentos. A execução foi organizada em 228 checkpoints de até 32 fragmentos, com inferência em lotes de oito. Cada checkpoint foi gravado atomicamente, permitindo interromper e retomar o processo sem recalcular lotes concluídos. O progresso foi registrado em `logs/corpus_embeddings.log`.

A execução final retomada ocorreu entre 13h21min31s e 15h13min37s de 12 de novembro de 2026, com duração de parede de 6.726,484 segundos. Considerando também os checkpoints produzidos antes da retomada, o tempo acumulado de inferência foi de 7.059,026 segundos. A taxa média registrada foi de 1,031 embedding por segundo, em CPU com seis threads.

Foram produzidos 7.276 vetores: 1.199 para a edição 1, 1.739 para a edição 2, 1.352 para a edição 3, 1.414 para a edição 4 e 1.572 para a edição 5. As contagens do tokenizer variaram de 108 a 804, com média de 475,50. Nenhum fragmento foi truncado e não houve identificador duplicado. As normas L2 ficaram entre 0,999999821 e 1,000000119, com média de 1,000000006.

### 10.6 Importação e validação integral

O arquivo consolidado possuía 103.298.218 bytes. Os vetores foram importados de forma idempotente por meio do script `sql/010_import_corpus_embeddings.sql`. A tabela passou a conter 7.276 embeddings para 7.276 fragmentos, sem registro ausente ou órfão. A função `vector_dims` confirmou 1.024 dimensões em todos os casos. As normas recalculadas no banco variaram de 0,999999847 a 1,000000161 e a maior distância de cosseno de um vetor para ele mesmo foi zero.

A distribuição por edição coincidiu com a segmentação. A relação `chunk_embeddings`, incluindo seus dados auxiliares, ocupou 43.360.256 bytes. Uma busca exata pelos dez vizinhos mais próximos, ainda sem índice aproximado, apresentou tempos de execução de 32,003 e 38,246 milissegundos em duas medições. Após a reinicialização do PostgreSQL, os 7.276 registros permaneceram disponíveis, confirmando a persistência.

### 10.7 Situação e limitações

Com essas evidências, a Etapa 5 foi considerada concluída. Todos os fragmentos possuem embeddings normalizados, rastreáveis e persistentes. A próxima etapa é construir a consulta semântica e avaliar a relevância dos resultados com perguntas e julgamentos humanos, conforme decisão metodológica do projeto.

Os testes realizados demonstram integridade numérica e operacional, mas não demonstram relevância semântica. Os tempos de busca foram obtidos em duas execuções locais sobre um corpus pequeno e não constituem uma análise de desempenho generalizável. A necessidade de índice HNSW será decidida somente após medir a recuperação exata durante a avaliação.

## 11 Etapa 6 - interface de recuperação e avaliação humana

### 11.1 Objetivo e princípio experimental

Foi construída uma interface web local para tornar observável a recuperação semântica e registrar julgamentos humanos de relevância. A interface não executa ainda a geração de respostas; sua função nesta etapa é isolar e avaliar o componente recuperador antes que seus resultados sejam fornecidos a um modelo gerador. Essa separação permite atribuir erros ao estágio correto: um trecho inadequado indica problema de recuperação, enquanto uma resposta inadequada produzida a partir de bons trechos indicará problema de geração ou de instrução.

A pergunta é codificada pelo mesmo BAAI/bge-m3, na mesma revisão fixada e com normalização L2 utilizada nos fragmentos. O vetor da consulta possui 1.024 dimensões. A recuperação usa o operador de distância de cosseno do pgvector e ordenação crescente, sem índice aproximado. A similaridade exibida ao avaliador é calculada como `1 - distância de cosseno`. Esse valor é apresentado como apoio descritivo; o julgamento humano não é derivado automaticamente dele.

### 11.2 Arquitetura e rastreabilidade

A aplicação local foi implementada com FastAPI 0.121.2, Uvicorn 0.38.0 e psycopg 3.2.12. O navegador comunica-se com uma API executada em `127.0.0.1:8765`; o serviço consulta o PostgreSQL já restrito ao computador local. O modelo é carregado do cache local e mantido em memória após o primeiro uso. Nenhum texto do corpus ou pergunta precisa ser enviado a um serviço externo para a recuperação.

O script `sql/011_retrieval_evaluation_schema.sql` introduziu três relações. `retrieval_runs` armazena pergunta, modelo, quantidade solicitada, vetor da consulta, tempos de vetorização e recuperação e instante da execução. `retrieval_results` preserva a posição, o fragmento e a distância de cosseno de cada item do ranking. `relevance_judgments` registra a classe atribuída pelo avaliador, uma observação opcional e o instante do julgamento. Chaves estrangeiras ligam cada julgamento a um resultado efetivamente retornado e cada resultado ao fragmento original.

Esse desenho registra o vetor da pergunta e o ranking observado, em vez de depender da repetição futura de uma consulta. Tal escolha preserva a evidência experimental mesmo que bibliotecas, configurações ou o corpus sejam alterados posteriormente. O julgamento utiliza atualização idempotente: uma segunda classificação para a mesma posição substitui a anterior, mantendo uma única decisão vigente e seu novo horário.

### 11.3 Operação da interface

A tela principal permite redigir uma pergunta em português e selecionar `top_k` entre 3, 5, 10, 15 ou 20. Cada resultado informa posição, similaridade, edição, página, índice do fragmento, participante, texto recuperado, identificador abreviado e acesso ao PDF original. O avaliador pode classificar o trecho como relevante, parcialmente relevante ou não relevante e acrescentar uma nota.

O critério operacional apresentado na própria interface define como relevante o trecho que responde diretamente ou fornece evidência essencial para a pergunta; parcialmente relevante o trecho relacionado ao tema, mas insuficiente ou indireto; e não relevante o trecho que não contribui para responder à pergunta. As telas de histórico e métricas mostram consultas já executadas, proporção avaliada e contagens por classe, facilitando o acompanhamento sem inspeção direta do banco.

O serviço mantém um log rotativo em `logs/web_interface.log`. O arquivo registra inicialização, carregamento do modelo, identificador da consulta, quantidade recuperada, tempos e julgamentos, sem duplicar o texto integral dos fragmentos. Essa política oferece rastreabilidade operacional com menor exposição desnecessária do conteúdo.

### 11.4 Validação funcional

A validação foi realizada em 13 de novembro de 2026 com o corpus integral: 3.969 documentos, 7.276 fragmentos e 7.276 embeddings. Duas perguntas controladas foram executadas com `top_k = 3`. Para a consulta de biodiversidade da Mata Atlântica, já com o modelo residente em memória, a vetorização levou 135,03 milissegundos e a recuperação exata levou 70,44 milissegundos. Os três primeiros resultados tratavam diretamente de espécies, conservação ou impactos climáticos no bioma consultado, constituindo uma verificação qualitativa inicial de coerência, sem pretensão de estimar a qualidade global.

Foram verificados o formulário de consulta, os cartões de resultados, o acesso aos controles de julgamento, a gravação e atualização da classificação, o histórico e as métricas agregadas. A persistência foi confirmada pela leitura posterior dos registros. As duas consultas e os dois julgamentos sintéticos usados no teste foram removidos ao final, deixando zero execução na base de avaliação para que a coleta humana comece sem contaminação. A evidência consolidada foi registrada em `artifacts/web_interface_validation_2026-11-13.json`.

### 11.5 Situação e limites

A implementação técnica da Etapa 6 está concluída e apta a iniciar a avaliação humana. Entretanto, nenhuma conclusão sobre precisão, recall ou utilidade pode ser formulada a partir das duas consultas funcionais. O próximo procedimento será definir e congelar um conjunto de perguntas, estabelecer avaliadores e protocolo de adjudicação e então coletar julgamentos suficientes para calcular métricas de recuperação. A geração de respostas somente será integrada após essa avaliação do recuperador.

## 12 Etapa 7 - linha de base do RAG com modelo de linguagem

### 12.1 Objetivo e delimitação

O objetivo desta etapa foi concluir um fluxo mínimo de RAG capaz de receber uma pergunta, recuperar evidências do corpus e produzir uma resposta com um modelo de linguagem. Essa implementação constitui a linha de base experimental do TCC. Ela não é apresentada como configuração ótima; será preservada para permitir que as melhorias posteriores sejam comparadas de forma controlada e reproduzível.

O fluxo implementado contém quatro operações sequenciais: codificação da pergunta pelo BAAI/bge-m3; recuperação exata dos cinco fragmentos com menor distância de cosseno; montagem de um contexto documental numerado; e geração da resposta por um modelo executado localmente no Ollama. Não foi introduzido reranqueamento nesta versão. A recuperação continua exclusivamente semântica.

### 12.2 Modelo gerador e parâmetros reproduzíveis

O gerador utiliza Ollama 0.40.16 e o modelo `llama3:latest`. O arquivo efetivamente instalado foi identificado pelo digest SHA-256 `365c0bd3c000a25d28ddbf732fe1c6add414de7275464c4e4d1c3b5fcb5d8ad1`. Trata-se de um modelo da família Llama com 8 bilhões de parâmetros, quantização Q4_0 e janela declarada de 8.192 tokens.

A geração foi configurada com temperatura igual a zero, semente 42, janela de contexto de 8.192 tokens e limite de 700 tokens de saída. O contexto textual foi limitado a 26.000 caracteres. Esses valores foram fixados no código, registrados para cada resposta e expostos pela interface. A temperatura zero reduz variação amostral, embora não constitua garantia absoluta de resultados idênticos entre versões diferentes do software, hardware ou arquivo do modelo; por esse motivo, o digest e a versão do Ollama também são preservados.

Todo o processamento ocorre no computador local. A pergunta e os trechos dos anais não são enviados a uma API externa. O serviço do Ollama é acessado pelo endereço local `127.0.0.1:11434`, e a aplicação web permanece em `127.0.0.1:8765`.

### 12.3 Construção do contexto e instrução do modelo

Cada evidência recebe um marcador estável durante a execução, no formato `[F1]`, `[F2]` e assim sucessivamente. O bloco enviado ao modelo contém edição, participante, página, índice do fragmento e texto. Quando dois fragmentos recuperados pertencem ao mesmo PDF, somente o primeiro é fornecido ao gerador nesta linha de base, evitando que um único trabalho seja contado como duas fontes independentes. O ranking integral permanece registrado e visível para auditoria.

O prompt de sistema, identificado como `rag-baseline-v1`, determina que a resposta use exclusivamente as fontes fornecidas, cite as afirmações factuais, não reproduza endereços de e-mail, declare insuficiência de evidência quando necessário e ignore comandos que possam aparecer dentro dos documentos. Também proíbe transferir título, autoria, objetivo, método ou resultado entre fontes diferentes. O hash SHA-256 do texto integral do prompt é registrado com cada resposta, permitindo verificar posteriormente se duas execuções utilizaram a mesma instrução.

### 12.4 Persistência e interface

O script `sql/012_generated_answers_schema.sql` criou as relações `generated_answers` e `answer_sources`. A primeira armazena a resposta, provedor, modelo, digest, versão e hash do prompt, temperatura, semente, limites, duração, contagens de tokens e metadados retornados pelo Ollama. A segunda liga cada fonte numerada ao resultado recuperado e ao fragmento original por chaves estrangeiras.

A interface passou a executar o fluxo completo pelo comando "Responder com RAG". A resposta é apresentada antes dos resultados de recuperação, acompanhada do modelo, fontes numeradas, links para os PDFs, identificador da execução, versão do prompt, parâmetros e tempo de geração. Os fragmentos permanecem disponíveis abaixo da resposta para julgamento humano de relevância.

### 12.5 Validação funcional e correção observada

A pergunta controlada foi: "Quais trabalhos abordam educação ambiental e quais foram seus principais objetivos?". Na primeira execução, o modelo produziu resposta e citações, mas associou a descrição de uma fonte ao título de outra. Esse erro foi registrado como evidência de que a presença de citações não garante, isoladamente, correção da atribuição.

Foi aplicada uma correção mínima antes de aceitar a linha de base: remoção de documentos duplicados do contexto e instruções explícitas para não combinar título, autoria ou objetivo entre fontes. Na validação final pela interface, a vetorização da pergunta levou 128,88 milissegundos, a recuperação exata levou 65,78 milissegundos e a geração local levou 7.172,31 milissegundos. O prompt processado possuía 3.468 tokens e a resposta produziu 323 tokens. A resposta final manteve coerência entre os trabalhos enumerados, seus objetivos e os marcadores citados.

Foram confirmados o funcionamento de ponta a ponta no navegador, o armazenamento da resposta, a ligação das fontes por chaves estrangeiras e o registro dos parâmetros. Os três experimentos sintéticos, identificados pelas execuções 7, 8 e 9, foram removidos após a validação. As quatro consultas anteriores do usuário foram preservadas. A evidência consolidada está em `artifacts/rag_llm_baseline_validation_2026-11-13.json`.

### 12.6 Limitações e continuidade

A validação comprova funcionamento técnico, não qualidade geral. Apenas uma pergunta foi inspecionada, não há reranqueador, o número de candidatos ainda é fixo e o modelo Llama 3 de 8 bilhões de parâmetros pode omitir fontes, confundir evidências ou produzir afirmações não sustentadas. A linha de base será mantida sem alterações retroativas. Durante o TCC, novas configurações serão comparadas sobre um conjunto congelado de perguntas, documentando ganhos provenientes de reranqueamento, expansão de contexto, modelos geradores, prompts, critérios de recusa e, futuramente, grafos para perguntas mais gerais e relacionais.

### 12.7 Correção da atribuição de autoria

Durante o uso da interface, a pergunta "cite os principais trabalhos que tem relação com IA" revelou um erro específico de atribuição. Para a fonte mais bem classificada, o modelo apresentou Barbosa e Bezerra, autores mencionados no corpo do resumo, como se fossem autores do trabalho dos anais. O registro do corpus identificava, entretanto, Alana Maqueise Silva Cruz como participante principal do trabalho `TECNOLOGIZAÇÃO DO MUNDO E SEUS DESDOBRAMENTOS NA EDUCAÇÃO`.

A causa foi a delegação ao modelo de linguagem da tarefa de distinguir metadados do documento e referências bibliográficas internas. Para corrigir o problema, o contexto passou a incluir a página integral do documento, em vez de apenas o fragmento recuperado. O título é extraído deterministicamente do cabeçalho, e o participante principal provém diretamente do manifesto importado para a tabela `documents`. Fontes com o mesmo título normalizado são removidas do contexto para evitar que o mesmo trabalho seja apresentado duas vezes.

A versão `rag-baseline-v1.4` separa duas responsabilidades. A aplicação constrói automaticamente um catálogo oficial com título, participante principal, edição e marcador `[F#]`; o modelo de linguagem produz apenas a síntese textual. Assim, a identificação bibliográfica exibida ao usuário não depende da interpretação do Llama 3. O texto bruto retornado pelo modelo também é preservado nos metadados da execução, enquanto a resposta final contém o catálogo determinístico e a síntese.

A repetição da pergunta confirmou que o catálogo passou a apresentar Alana Maqueise Silva Cruz, Ana Luisa Abade Santos, Anna Ritha Figueiredo Rodrigues Pinto Coelho e Laís Santos Gomes, associados aos títulos e edições registrados no corpus. Os testes também mostraram que a síntese livre do Llama 3 ainda pode transferir conteúdo temático entre fontes, mesmo quando a autoria está correta. Essa limitação permanece explicitamente registrada e deverá ser tratada na otimização posterior por avaliação humana, reranqueamento, decomposição da geração por fonte ou adoção de modelo gerador mais competente.

### 12.8 Inclusão do orientador na apresentação das fontes

A versão `rag-baseline-v1.5` ampliou o catálogo determinístico para apresentar título, autor principal, orientador, edição e marcador `[F#]`. O orientador não é produzido pelo modelo de linguagem. A aplicação lê o cabeçalho da página, localiza a afiliação marcada como `Orientador(a)` e relaciona o número dessa afiliação ao nome numerado na lista de autores. A mesma informação é incluída no contexto como campo explícito e devolvida pela API junto às fontes da resposta.

A verificação integral identificou automaticamente o orientador em 3.965 dos 3.969 cabeçalhos que contêm a marcação, correspondendo a 99,9%. Nos quatro casos restantes, o arquivo original não oferece um nome que possa ser relacionado com segurança; por isso, a interface registra `não identificado no cabeçalho`, sem inferência. Para manter o relatório parcial conciso, as dez respostas completas do experimento permaneceram preservadas no banco de dados e nos registros de execução, enquanto o PDF passou a apresentar apenas a configuração, a tabela de similaridades e a interpretação preliminar.

## 13 Riscos e medidas de controle

- Falha de extração textual: páginas com pouco texto ou caracteres inválidos serão separadas para avaliação de OCR.
- Perda de proveniência: todos os fragmentos deverão manter identificadores de documento, edição e página.
- Respostas sem suporte: o prompt exigirá citações e declaração de insuficiência de evidência.
- Exposição de dados pessoais: informações como endereços de e-mail não deverão ser reproduzidas nas respostas.
- Irreprodutibilidade: versões, parâmetros, hashes e identificadores de execução serão registrados.
- Viés de avaliação: as perguntas e os julgamentos de relevância serão revisados por humanos e congelados por versão.

## Referências

LEWIS, Patrick et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. Advances in Neural Information Processing Systems, v. 33, p. 9459-9474, 2020. Disponível em: https://arxiv.org/abs/2005.11401.

CHEN, Jianlv et al. M3-Embedding: Multi-Linguality, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation. arXiv:2402.03216, 2024. Disponível em: https://arxiv.org/abs/2402.03216. Acesso em: 12 nov. 2026.

GRATTAFIORI, Aaron et al. The Llama 3 Herd of Models. arXiv:2407.21783, 2024. Disponível em: https://arxiv.org/abs/2407.21783. Acesso em: 13 nov. 2026.

OLLAMA. API Reference. 2026. Disponível em: https://github.com/ollama/ollama/blob/main/docs/api.md. Acesso em: 13 nov. 2026.

PGVECTOR. Open-source vector similarity search for PostgreSQL. 2026. Disponível em: https://github.com/pgvector/pgvector. Acesso em: 11 nov. 2026.

POSTGRESQL GLOBAL DEVELOPMENT GROUP. PostgreSQL 17 Documentation. Disponível em: https://www.postgresql.org/docs/17/. Acesso em: 11 nov. 2026.

