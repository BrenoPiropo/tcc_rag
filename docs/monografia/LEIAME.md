# Fontes da monografia

O arquivo principal é [`modelo_anais.tex`](modelo_anais.tex). A versão para leitura está em [PDF](../../output/pdf/TCC_Anais_SIC_UESC_RAG.pdf).

Compile nesta pasta com uma distribuição LaTeX que inclua XeLaTeX, BibTeX, as dependências indicadas no arquivo principal e a fonte Arial.

```text
xelatex modelo_anais.tex
bibtex modelo_anais
xelatex modelo_anais.tex
xelatex modelo_anais.tex
```

`monografia_sic_uesc.cls` é uma adaptação da classe legada `monografia.cls`, de Maxwell Mariano de Barros (UFMA). Mantém as atribuições originais e usa nome próprio segundo o aviso de licença do arquivo. A adaptação ajusta os elementos pré-textuais e a paginação do trabalho. O texto da licença está na [LaTeX Project Public License](https://www.latex-project.org/lppl/). Uma cópia da classe de origem é identificada na [publicação que reproduz a classe da UFMA](https://gist.github.com/guilhermebferreira/72e2d9a3631097597e13b4e84d4e2c64).
