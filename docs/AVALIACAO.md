# Avaliação e defesa do TDE

## Relação com o enunciado

| Requisito | Evidência implementada |
|---|---|
| ML — 10% | Dois classificadores supervisionados, comparação de algoritmos, validação por grupo, macro-F1 e matriz de confusão. Experimento com um modelo neural zero-shot (Qev 0.8B) no mesmo conjunto de teste. |
| LLM — 10% | Ollama local: resumo, ação, extração de prazo e rascunho com JSON validado. |
| Sistema completo — 25% | OAuth/importação → normalização → SQLite → ML → LLM → interface → correção/retreino. |
| Ética — 5% | Origem dos dados explícita, análise local, mínimos privilégios, evidências de prazo, revisão humana e limites documentados. |

## Preparação dos dados reais

1. Obter autorização para usar as mensagens. Não incorporar e-mails de terceiros indiscriminadamente.
2. Desidentificar nomes, telefones, números de documento e outros elementos desnecessários antes de compartilhar qualquer amostra com o grupo. Substituir apenas nomes não garante anonimização.
3. Registrar `group_id` por conversa; mensagens encaminhadas, duplicatas e variantes do mesmo texto devem permanecer no mesmo grupo.
4. Rotular uma amostra de forma independente por dois integrantes, discutir divergências e calcular concordância. O aplicativo não implementa automaticamente essa etapa humana.
5. Buscar 300–500 mensagens representativas como estudo inicial, incluindo algumas dezenas por classe. A qualidade e a diversidade importam mais que o número isolado.
6. Importar CSV e registrar versão do corpus, data e critérios usados. Evitar reimportar a mesma conversa com outro identificador.

## Guia de anotação sugerido

Categorias se referem ao propósito predominante da mensagem:

- **Faculdade:** disciplinas, trabalhos, notas, matrícula, biblioteca universitária.
- **Trabalho:** entregas profissionais, clientes, equipe, fornecedores e decisões de projeto.
- **Financeiro:** faturas, cobranças, extratos, recibos, pagamentos e reembolsos. Uma cobrança de faculdade entra aqui por seu propósito financeiro.
- **Pessoal:** família, amigos, compromissos privados, viagens e serviços pessoais.
- **Promoções:** publicidade, ofertas e newsletters; palavras como “urgente” e “última chance” não criam obrigação por si só.

Prioridade inicial é anotada no instante de recebimento:

- **Urgente:** exige ação explícita em até 24 horas ou relata um problema que demanda intervenção imediata.
- **Normal:** pede ação/retorno sem urgência imediata ou tem relevância operacional.
- **Baixa:** informação sem ação pendente, promoção não solicitada ou confirmação de assunto concluído.

Se não há contexto suficiente, registrar a dúvida e resolver por adjudicação antes de incluir o exemplo no conjunto final. “Remetente institucional” sozinho não torna um e-mail urgente.

## Avaliação implementada

TF-IDF de palavras e bigramas (até 18 mil features) unido a n-gramas de caracteres de 3 a 5 (até 40 mil), que toleram flexões e erros de digitação. Os indícios mostrados ao usuário vêm apenas das palavras. Modelos candidatos: Regressão Logística com pesos balanceados, Naive Bayes e SVM linear com pesos balanceados; classe majoritária como referência. Treino local sem ajuste de LLM.

Partição determinística por grupo: cerca de 60% treino, 20% validação, 20% teste. A proporção efetiva pode variar, especialmente em bases pequenas. Seleção por macro-F1 na validação; teste permanece fora da seleção. O relatório JSON inclui scores por classe, suporte, matriz de confusão e comparações.

O corpus de partida (`backend/corpus.py`, versão 2) tem 450 exemplos sintéticos provenientes de 150 cenários: 30 por categoria, cada cenário nas três prioridades. Cada e-mail tem assunto, saudação, tema, frase de contexto do domínio, frase de prioridade (pedido + prazo, ou ausência de ação) e remetente. As frases do treino e as da validação/teste vêm de conjuntos disjuntos; o vocabulário de domínio ("disciplina", "fatura", "hoje", "sem pressa") se repete, como em e-mails reais, mas nenhuma frase inteira. Um teste automatizado garante essa separação e a presença de todas as classes em todas as partições.

O corpus inclui casos difíceis de propósito: mensalidade da faculdade rotulada como financeiro (pelo guia de anotação), "trabalho final" de uma disciplina, promoções com "só hoje", mensagens sem pendência que mencionam "hoje" e negações como "nada urgente".

| Tarefa | Modelo selecionado | Macro-F1 validação | Macro-F1 teste | Acurácia teste | Classe majoritária (validação) |
|---|---|---|---|---|---|
| Categoria | Regressão logística | 0,99 | 0,86 | 0,87 | 0,05 |
| Prioridade | Naive Bayes | 0,80 | 0,79 | 0,82 | 0,19 |

Erros restantes no teste: 7 de 24 e-mails de faculdade previstos como trabalho (estágio, seminário, "trabalho final") e o recall de **urgente** em 52% (14 de 27), com urgências sem as palavras vistas no treino ("até o fim do dia", "não haverá prorrogação") lidas como normal ou baixa. Para um assistente de prioridade, esse é o erro mais caro: a interface mantém a mensagem original visível, e um prazo confirmado pelo usuário para as próximas 24 horas torna a mensagem urgente independentemente do classificador.

Na versão 1 do corpus (180 exemplos, um template fixo por prioridade e o tema como único sinal de categoria), o teste dava macro-F1 0,53 para categoria e 1,00 para prioridade. O 1,00 era memorização do template, e a partição de teste não tinha nenhum e-mail de trabalho. As métricas atuais continuam sendo **verificação do pipeline** com dados sintéticos, não desempenho comprovado no mundo real.

### Comparação com um modelo de decisão zero-shot (Qev)

O [Qev 0.8B](https://huggingface.co/twainsk/qev-0.8b) (Apache-2.0) é uma alternativa aberta e local ao Jev, da TypeSafe: um adaptador LoRA e uma cabeça de ponteiro sobre o Qwen3.5-0.8B, que escolhe entre opções fornecidas e devolve probabilidades, **sem gerar texto**. Ele **não foi treinado nestes e-mails**. As opções de resposta são as definições do guia de anotação acima. A redação das perguntas (português ou inglês) foi escolhida por tarefa na validação; só então o teste foi medido, como nos modelos TF-IDF.

| Teste (105 e-mails) | TF-IDF (treinado no corpus) | Qev 0.8B (zero-shot) |
|---|---|---|
| Categoria, macro-F1 | 0,86 | **0,91** |
| Prioridade, macro-F1 | **0,79** | 0,64 |
| Recall de **urgente** | 52% (14 de 27) | **70% (19 de 27)** |
| Recall de baixa | **88% (38 de 43)** | 30% (13 de 43) |
| Treino | segundos, no próprio corpus | nenhum |
| Tempo por e-mail | milissegundos, CPU | 0,65 s (2 perguntas, GPU do Mac via MPS) |
| Tamanho | 1,3 MB | 1,8 GB + PyTorch |

Leitura:

- Sem nenhum exemplo de treino, o Qev supera o classificador treinado em categoria e corrige a principal confusão: 22 de 24 e-mails de faculdade certos, contra 17 de 24.
- Em prioridade, perde no geral, mas encontra mais urgentes, que é o erro mais caro para o usuário. Sua fraqueza é a oposta: 27 de 43 mensagens de baixa prioridade viram normal.
- Português superou inglês nas duas tarefas (validação: categoria 0,96 contra 0,93; prioridade 0,72 contra 0,65), embora o Qev tenha sido treinado em inglês e chinês.
- Não há vencedor único: o modelo pequeno treinado no domínio e o modelo neural genérico erram de formas diferentes.

Limitações: corpus sintético e apenas 105 e-mails de teste; o Qev é um projeto novo de um único autor, publicado em setembro de 2026, sem avaliação independente (o código do runtime foi revisado e o commit fixado antes da execução); exige PyTorch e cerca de 1,8 GB, e o desempenho na CPU do i7-1260P não foi medido; não oferece indícios por palavra como o modelo linear, só probabilidades; parte dos dados de treino do Qev tem licenças share-alike ou não declaradas, segundo o próprio cartão do modelo.

### Combinação TF-IDF + Qev

Como os dois modelos erram de formas diferentes, combinamos suas probabilidades. Foram comparados: média ponderada, combinação log-linear (produto ponderado, que lida melhor com as probabilidades extremas do Naive Bayes), stacking (regressão logística sobre as log-probabilidades, avaliada por validação cruzada por grupo) e, para prioridade, o TF-IDF com um alerta de urgência do Qev acima de um limiar. **Pesos, limiares e o próprio método foram escolhidos só na validação**; o teste foi lido uma única vez, no fim.

| Teste (105 e-mails) | TF-IDF | Qev | **Combinação escolhida na validação** |
|---|---|---|---|
| Categoria, macro-F1 | 0,86 | 0,91 | **0,94** (média ponderada, peso 0,8 para o TF-IDF) |
| Prioridade, macro-F1 | 0,79 | 0,64 | **0,85** (log-linear, peso 0,75 para o TF-IDF) |
| Recall de urgente | 52% | 70% | **74%** |
| Recall de baixa | 88% | 30% | 79% |

Todos os métodos de combinação superaram os dois modelos isolados nas duas tarefas. No teste, o stacking (0,91) e o alerta de urgência (0,91, com 96% de recall de urgente) foram ainda melhores em prioridade, mas não foram os escolhidos na validação, e trocar de método depois de olhar o teste seria contaminar a avaliação. A validação tem só 93 e-mails (31 grupos): as diferenças entre os métodos de combinação estão dentro do ruído, e em categoria ela chega ao teto (1,00). A conclusão robusta é que combinar os dois modelos é melhor do que qualquer um sozinho, não qual combinação é a melhor.

O experimento completo (Qev sozinho, probabilidades por e-mail e combinação) é reproduzível com `./experiments/qev/run.sh`; runtime e modelos ficam em `.local-data/qev` e os resultados em `artifacts/qev-*.json`.

**No aplicativo:** com o Qev instalado (`preparar_qev`), o Foco repete esse protocolo sozinho. O Qev responde a validação e o teste, o modelo é retreinado e a combinação é escolhida na validação; a área **Inteligência & dados** passa a mostrar "TF-IDF + Qev" como modelo selecionado. Na execução real no Mac, o aplicativo escolheu as mesmas combinações do experimento e obteve os mesmos números no teste (categoria 0,935; prioridade 0,846). Sem o Qev, o aplicativo usa só o TF-IDF.

Ao importar dados, o relatório é de escopo misto. Para sustentar uma alegação sobre uso pessoal, mantenha um conjunto real adicional, congelado e nunca utilizado para ajuste. Relate separadamente desempenho em diferentes contas/remetentes e em um período posterior. Evite escolher exemplos apenas porque o modelo já os classificou bem.

As probabilidades da Regressão Logística não foram calibradas para o domínio pessoal. A interface mostra indícios do classificador em vez de exibir porcentagens como certeza. As palavras com peso positivo são indícios estatísticos, não uma explicação causal.

## Avaliação do LLM

Montar pelo menos 30 mensagens de teste revisadas manualmente, cobrindo:

| Caso | Verificação |
|---|---|
| Prazo absoluto | Data coincide com o trecho da mensagem. |
| Prazo relativo | “Amanhã” usa a data de envio e seu fuso. |
| Prazo ausente | O sistema não inventa uma data. |
| Prazo ambíguo | A interface exige revisão; a data não deve ser apresentada como confirmada. |
| Publicidade urgente | Não converter chamada comercial em obrigação. |
| Histórico citado | Conferir se a ação atual não foi confundida com um pedido antigo. |
| Instrução maliciosa no texto | Não executar ações, ferramentas ou divulgar outras mensagens. |
| Mensagem longa | Mostrar truncamento e possibilitar leitura do original. |
| Rascunho | Não afirmar pagamentos, entregas ou compromissos concluídos sem evidência. |

Medir fidelidade factual, ações omitidas/inventadas, acerto de prazo, proporção de saídas inválidas, latência e memória. JSON válido não garante fatos corretos. A validação exige evidência literal para manter um prazo; ainda assim, a interpretação desse trecho pode estar errada e o usuário precisa confirmá-lo.

Salvaguardas em código, aplicadas depois do LLM. Todas nasceram de erros reais observados com os e-mails de demonstração:

| Erro observado | Salvaguarda |
|---|---|
| Golpe pedindo senha virou a ação "enviar senha" | Ações com senha, código de verificação, token ou dados de cartão são descartadas e substituídas por um alerta de possível golpe. "Código de barras" de boleto não é afetado. |
| Promoção "só hoje" virou prazo e ação | Mensagens classificadas como promoção não geram ação nem prazo, como já dizem o prompt e o guia de anotação. |
| Prazo no ano 2100 com evidência literal correta | Prazo fora do intervalo de um dia antes a um ano depois do envio é descartado. |
| Ação "null" escrita como texto manteve um prazo cuja evidência dizia "não há prazo" | Ações vazias escritas como texto ("null", "nenhuma") contam como ausência de ação. |

Limitações que continuam: datas por dia da semana ("até sexta") às vezes caem um dia antes; o fuso às vezes vem em UTC em vez de −03:00; frases como "se já pagou, desconsidere" podem virar a ação. Por isso o prazo sempre exige confirmação do usuário.

O teste real automatizado em `scripts/smoke_ai.py` verifica apenas um cenário de prazo relativo e geração de rascunho. Isso é evidência funcional, não uma avaliação abrangente da qualidade do LLM.

## Roteiro de demonstração (8–10 minutos)

1. **Problema (1 min):** várias contas e decisões misturadas; apresentar Meu dia.
2. **Entrada (1 min):** mostrar contas e importar uma mensagem `.eml` nova.
3. **ML (2 min):** abrir classificação, corrigir um rótulo, mostrar comparação e matriz de confusão (com o Qev: TF-IDF, Qev e "TF-IDF + Qev"). Explicitar quais dados são sintéticos e quais são reais. Na promoção ao vivo "só hoje", o Qev sozinho diria urgente e a combinação corrige para baixa.
4. **LLM (2 min):** analisar a "Revisão do relatório" ao vivo, conferir a evidência do prazo e criar um rascunho. Deixar o modelo carregado antes de apresentar.
5. **Saída e integração (1 min):** confirmar prazo, concluir uma ação, filtrar outra conta e recarregar a página para demonstrar persistência.
6. **Ética e limites (1 min):** analisar o golpe ao vivo "Confirme seus dados de acesso". O LLM ignora a instrução embutida e o Foco troca "enviar senha" por um alerta. Mostrar também o original, a revisão humana, a ausência de envio automático e as incertezas.
7. **Evidência local (1 min):** com dependências/modelo previamente instalados, desconectar a rede e gerar uma análise nova. Conectores precisam de rede; IA local não.

Preparar um conjunto demonstrativo sem dados pessoais e um vídeo de contingência identificado como gravação. Não depender de autorização OAuth ao vivo no dia da defesa.
