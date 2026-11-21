from __future__ import annotations

import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
INPUT_JSON = PROJECT_ROOT / "artifacts" / "avaliacao_rag_versao_1_10_perguntas.json"
OUTPUT_TEX = WORKSPACE_ROOT / "Relatorio_Parcial_LaTeX_UESC_Anais" / "experimento_rag_v1.tex"


def latex_escape(value: str) -> str:
    value = (
        value.replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u00a0", " ")
    )
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def main() -> None:
    record = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    responses = record["responses"]
    questions = record["questions"]

    lines: list[str] = []
    lines.extend(
        [
            r"\section{Experimento temático da Versão 1}",
            "",
            (
                "Em 13 de novembro de 2026, a linha de base foi submetida a dez perguntas temáticas "
                "definidas para representar consultas amplas sobre o corpus. Cada pergunta foi codificada "
                "pelo BAAI/bge-m3 e comparada aos 7.276 fragmentos. O recuperador selecionou os cinco "
                "menores valores de distância de cosseno no pgvector. Em seguida, o modelo "
                r"\texttt{llama3:latest} recebeu as fontes selecionadas e produziu a resposta. As execuções "
                "correspondem aos identificadores 15 a 24 e foram preservadas sem correção manual, "
                "constituindo a Versão 1 do experimento."
            ),
            "",
            r"\subsection{Uso da similaridade de cosseno}",
            "",
            (
                "A similaridade foi utilizada exclusivamente para ordenar os fragmentos candidatos. "
                "Sejam $\\mathbf{q}$ o vetor da pergunta e $\\mathbf{d}_{i}$ o vetor do fragmento. "
                "A aplicação calculou a distância de cosseno por meio do operador do pgvector e apresentou "
                "a similaridade como:"
            ),
            "",
            r"\begin{equation}",
            r"\operatorname{similaridade}(\mathbf{q},\mathbf{d}_{i}) = 1 - \operatorname{distancia}_{\cos}(\mathbf{q},\mathbf{d}_{i}).",
            r"\end{equation}",
            "",
            (
                "Quanto maior o valor, maior a proximidade semântica estimada entre a consulta e o fragmento. "
                "A pontuação não representa probabilidade de correção, não comprova que a fonte responde à "
                "pergunta e não avalia a fidelidade do texto gerado. Sua função nesta etapa foi determinar o "
                "ranking inicial das evidências. A relevância e a correção continuam dependentes de julgamento "
                "humano. A Tabela~\\ref{tab:similaridades-v1} registra os cinco primeiros valores de cada consulta."
            ),
            "",
            r"\begin{table}[htbp]",
            r"\centering",
            r"\caption{Similaridade de cosseno dos cinco primeiros fragmentos recuperados na Versão 1}",
            r"\label{tab:similaridades-v1}",
            r"\setlength{\tabcolsep}{2.2pt}",
            r"\renewcommand{\arraystretch}{1.2}",
            r"\scriptsize",
            r"\begin{tabularx}{\textwidth}{|c|>{\raggedright\arraybackslash}X|*{5}{>{\centering\arraybackslash}p{1.15cm}|}}",
            r"\hline",
            r"\rowcolor{blue!25}",
            r"\textbf{Nº} & \textbf{Pergunta} & \textbf{1º} & \textbf{2º} & \textbf{3º} & \textbf{4º} & \textbf{5º} \\ \hline",
        ]
    )
    for number, (question, response) in enumerate(zip(questions, responses), start=1):
        similarities = [float(result["similarity"]) * 100 for result in response["results"]]
        score_cells = " & ".join(f"{score:.2f}\\%".replace(".", ",") for score in similarities)
        lines.append(f"{number} & {latex_escape(question)} & {score_cells} \\\\ \\hline")
    lines.extend(
        [
            r"\end{tabularx}",
            r"\end{table}",
            "",
            (
                "Entre os primeiros resultados, a maior pontuação foi observada na pergunta 9 "
                "($62{,}98\\%$), e a menor na pergunta 2 ($55{,}28\\%$). Esses extremos descrevem "
                "somente a distribuição do ranking desta execução e não devem ser interpretados como "
                "medidas diretas da qualidade das respostas."
            ),
            "",
            r"\subsection{Apresentação das fontes nas respostas}",
            "",
            (
                "As respostas integrais foram preservadas no banco de dados e nos registros de execução, mas "
                "não são reproduzidas neste relatório para evitar extensão excessiva. A apresentação das fontes "
                "foi ajustada para exibir, em cada trabalho recuperado, título, autor principal, orientador, "
                "edição e marcador de citação. O autor principal provém do metadado do participante e o nome "
                "do orientador é extraído deterministicamente do cabeçalho do documento, a partir da indicação "
                r"\textit{Orientador(a)}. Portanto, esses nomes não são inferidos pelo modelo de linguagem."
            ),
            "",
        ]
    )

    lines.extend(
        [
            r"\subsection{Interpretação preliminar}",
            "",
            (
                "O experimento demonstrou que a linha de base executa o fluxo completo de recuperação, "
                "montagem de contexto, geração e citação. Entretanto, as respostas devem ser consideradas "
                "resultados preliminares. A pontuação de cosseno foi suficiente para selecionar candidatos "
                "semanticamente próximos, mas não impediu fontes apenas parcialmente relacionadas nem garante "
                "que o modelo associe cada afirmação à fonte correta. Esses resultados serão usados como "
                "referência para as avaliações humanas e para as otimizações posteriores."
            ),
            "",
        ]
    )
    OUTPUT_TEX.write_text("\n".join(lines), encoding="utf-8")
    print(OUTPUT_TEX)


if __name__ == "__main__":
    main()
