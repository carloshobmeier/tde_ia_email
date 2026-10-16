# Roteiro de fala: proposta do TDE 2, Assistente de e-mail local

**Duração alvo:** cerca de 8 min e 45 s. Cabe nos 10 minutos com folga e pode ser cortado para 5 (ver o fim deste arquivo).
**Ritmo de referência:** cerca de 140 palavras por minuto, sem correr.

As falas entre aspas são um guia e não precisam ser decoradas. Legenda:
- **[avançar]**: passe para o próximo slide.
- *[apontar: ...]*: mostre esse elemento na tela.

## Divisão sugerida

| Slides | Quem | Tempo |
|---|---|---|
| 1 a 3: abertura, problema, proposta | Amanda | 1:45 |
| 4 e 5: arquitetura e machine learning (o foco) | Carlos | 4:20 |
| 6 a 9: LLM, saída, ética, cronograma | João | 2:40 |

É só uma sugestão, troquem à vontade. Quem apresentar os slides 4 e 5 deve ler com atenção as perguntas prováveis desses slides: é ali que os professores costumam fazer perguntas.

---

## Slide 1: Capa (0:25)

> "Boa noite. Somos Amanda, Carlos e João, e a nossa proposta para o TDE 2 é um assistente de e-mail que roda localmente, no próprio computador da pessoa. Ele lê a caixa de entrada, entende o que é urgente e diz o que fazer primeiro."

**[avançar]**

## Slide 2: O problema (0:40)

> "Todo mundo conhece esta situação: a caixa de entrada é organizada por ordem de chegada. O e-mail avisando que o prazo do relatório é amanhã às 9h chega misturado com newsletter, promoção, fatura e convite."

*[apontar: carimbo URGENTE no meio da pilha]*

> "A gente acaba lendo tudo para achar o que importa ou, pior, não vê a tempo. O problema não é a quantidade de e-mails: é que a ordem de leitura não reflete a importância."

**[avançar]**

## Slide 3: A proposta (0:40)

> "O assistente faz três coisas. Primeiro, **classifica** cada e-mail por urgência e por categoria: essa é a parte de machine learning. Depois, **resume** o essencial em até duas linhas e **sugere** a resposta e a próxima ação: essa é a parte do modelo de linguagem, que roda localmente. E um ponto importante: o assistente sugere, mas quem decide e quem envia é sempre a pessoa."

> "Agora, Carlos mostra como isso funciona por dentro."

**[avançar]**

---

## Slide 4: Arquitetura, entrada → processamento → saída (2:10) ⭐

**Objetivo do slide:** provar que é um **sistema completo** (25% da nota) e justificar a ordem **ML antes do LLM**.

> "Este slide é o coração do sistema: o caminho que cada e-mail percorre. São quatro estações."

*[apontar: 01 ENTRADA]*

> "**Entrada.** O sistema lê os e-mails direto da caixa pelo protocolo IMAP, que é o padrão do Gmail, do Outlook e de praticamente todos os provedores. Também dá para usar arquivos .eml exportados. O acesso é **somente leitura**: o assistente não apaga, não move e não envia nada. De cada mensagem extraímos remetente, assunto, data e o corpo em texto puro. Depois fazemos uma limpeza: tiramos HTML, assinaturas e o histórico de respostas citadas, que só atrapalham o modelo."

*[apontar: 02 ML]*

> "**Machine learning.** O texto limpo passa por dois classificadores, que eu detalho no próximo slide: um diz a urgência e o outro, a categoria."

*[apontar: 03 LLM]*

> "**LLM.** Aí entra o modelo de linguagem, rodando localmente com o Ollama. Ele recebe o e-mail já com os rótulos e devolve, em formato estruturado, o resumo, as ações e prazos e um rascunho de resposta.
> Aqui tem uma decisão de projeto importante. O ML roda em **todos** os e-mails, porque é rápido e leve. O LLM é mais pesado e só processa o que precisa: uma promoção de baixa prioridade, por exemplo, não precisa de resumo nem de resposta. É isso que torna o sistema viável num notebook comum."

*[apontar: 04 SAÍDA]*

> "**Saída.** Tudo aparece num painel feito em Streamlit: uma fila ordenada por prioridade, com resumo, ação sugerida e a resposta pronta para revisar. Quando a pessoa corrige uma classificação, a correção fica guardada num banco local e vira dado de treino para melhorar o modelo."

*[apontar: linha STACK PREVISTA]*

> "Tudo em Python: scikit-learn para o ML, Ollama para o LLM e Streamlit para a interface."

**[avançar]**

### Perguntas prováveis sobre o slide 4

- **"Por que não mandar tudo direto para o LLM?"**
  Por três motivos:
  1. **Custo computacional:** um LLM local é lento para centenas de e-mails.
  2. **Avaliação:** um classificador supervisionado pode ser medido com F1 e matriz de confusão, enquanto um LLM é mais difícil de avaliar e de reproduzir.
  3. **Divisão de papéis:** cada técnica faz o que faz melhor.

  Bônus: podemos usar o LLM sem treino (zero-shot) como **comparação** com o nosso classificador.
- **"Precisa da senha do e-mail?"**
  Para IMAP, usamos uma senha de app ou OAuth, guardada só na máquina. Na demonstração podemos usar arquivos .eml, sem conectar em conta nenhuma.
- **"E se o computador for fraco?"**
  Modelos pequenos (de 3 a 8 bilhões de parâmetros) e quantizados rodam em notebook com 8 a 16 GB de RAM. Fica mais lento, mas funciona. E como o LLM só processa parte dos e-mails, o volume é menor.
- **"O sistema responde sozinho?"**
  Não. Ele gera o rascunho, e a pessoa revisa e envia. Isso é uma decisão de projeto e volta no slide de ética.

---

## Slide 5: Machine learning (2:10) ⭐

**Objetivo do slide:** mostrar que o ML é de verdade (10% da nota), com tarefa, modelo, dados e avaliação.

> "Esta é a parte de machine learning. Separamos o problema em duas perguntas, e cada uma vira um classificador supervisionado."

*[apontar: "Quão urgente?"]*

> "A primeira: **quão urgente** é este e-mail? São três classes: urgente, normal e baixa."

*[apontar: "Sobre o quê?"]*

> "A segunda: **sobre o que** ele é? Cinco categorias: faculdade, trabalho, financeiro, pessoal e promoções.
> Por que dois modelos e não um? Porque são dimensões independentes: um e-mail da faculdade pode ser urgente ou não, e uma fatura pode vencer hoje ou daqui a um mês."

*[apontar: MODELO]*

> "O modelo de partida é **TF-IDF com Regressão Logística**, do scikit-learn. O TF-IDF transforma o assunto e o corpo em números e dá peso às palavras que distinguem um e-mail dos outros, como 'prazo', 'amanhã', 'fatura' ou 'desconto'. Escolhemos a Regressão Logística porque é rápida, funciona bem com texto e é **interpretável**: dá para ver quais palavras pesaram na decisão. Vamos comparar com Naive Bayes e SVM linear e ficar com o melhor."

*[apontar: DADOS]*

> "Os **dados** são e-mails reais dos integrantes, **anonimizados**: nomes, endereços e telefones são trocados antes de tudo. Nós mesmos rotulamos, seguindo um guia com critérios escritos. Por exemplo: 'urgente' é o que exige ação em até 24 horas."

*[apontar: AVALIAÇÃO]*

> "Para **avaliar**, separamos uma parte para teste e usamos **F1-score** e **matriz de confusão**. Usamos F1 porque as classes são desbalanceadas: a maioria dos e-mails não é urgente, então a acurácia sozinha engana. A matriz de confusão mostra o erro que mais nos preocupa: um e-mail urgente classificado como baixa prioridade. Esse é o erro caro, e vamos ajustar o modelo para não perder os urgentes."

> "Agora, João explica a parte do modelo de linguagem."

**[avançar]**

### Perguntas prováveis sobre o slide 5

- **"Quantos e-mails vocês vão rotular?"**
  A meta é de 300 a 500 e-mails, com pelo menos algumas dezenas por classe. *(Ajustem para o número que for viável para vocês.)* Se uma classe ficar pequena (provavelmente "urgente"), usamos pesos por classe (`class_weight="balanced"`) para compensar.
- **"Urgência é subjetiva. Como garantir rótulos consistentes?"**
  Com um guia de rotulagem de critérios objetivos: prazo em até 24h, pedido explícito de resposta, remetente institucional. Além disso, dois integrantes rotulam a mesma amostra e medimos a concordância (kappa de Cohen).
- **"Por que não deep learning, tipo BERT?"**
  Com poucas centenas de exemplos, um modelo clássico costuma ser competitivo e é muito mais leve. Se sobrar tempo, testamos embeddings de um modelo pré-treinado como features, mas o baseline vem primeiro.
- **"Por que não um dataset público?"**
  Os conhecidos, como o Enron, estão em inglês e vêm de um contexto corporativo diferente. Podem complementar, mas o nosso cenário é e-mail de estudante em português.
- **"Qual resultado vocês consideram bom?"**
  Mais do que um número único, queremos **recall alto na classe urgente**: é melhor marcar um e-mail normal como urgente do que deixar passar um urgente.

---

## Slide 6: LLM local (0:45)

> "Na parte de LLM, usamos um modelo aberto, como Llama, Qwen ou Gemma, rodando localmente pelo Ollama. Ele tem três tarefas: resumir o e-mail em até duas linhas, extrair ações e prazos e rascunhar uma resposta.
> Por que local, e não uma API na nuvem? Porque e-mail é dado pessoal: rodando na máquina, nada vai para a nuvem. Além disso, não tem custo por uso e funciona offline."

**[avançar]**

## Slide 7: Exemplo de saída (0:40)

> "É isto que a pessoa vê de manhã. No topo está o e-mail mais urgente: a coordenação antecipou o prazo do relatório. O sistema mostra o resumo, a ação sugerida e uma resposta pronta."

*[apontar: botão REVISAR E ENVIAR]*

> "Reparem no botão: é 'revisar e enviar', não 'enviar'. Ao lado está o resto da fila: a fatura, a ata da reunião e, por último, as promoções, que podem ser arquivadas em lote. Este é um exemplo ilustrativo de como vai ser a saída."

**[avançar]**

## Slide 8: Ética e responsabilidade (0:45)

> "Sobre ética, são quatro pontos.
> **Privacidade:** tudo roda localmente, em linha com a LGPD, e os dados de treino são anonimizados.
> **Humano no controle:** o assistente sugere, mas nunca envia nada sozinho.
> **Transparência:** mostramos por que um e-mail foi classificado como urgente, ou seja, as palavras que mais pesaram.
> **Limites:** o modelo pode errar, o LLM pode inventar informação (a chamada alucinação) e os rótulos refletem o critério de quem rotulou, que somos nós três. Por isso a revisão humana não é opcional."

**[avançar]**

## Slide 9: Cronograma e encerramento (0:30)

> "Até a defesa, em 26 de outubro: até 5/10, dados rotulados e classificador treinado; até 12/10, o LLM integrado; até 19/10, interface e testes. No dia 26, a demonstração funcionando.
> Obrigado. Estamos abertos a perguntas."

---

## Versão de 5 minutos (se o tempo for cortado)

| Slide | Tempo | O que cortar |
|---|---|---|
| 1 | 0:15 | Fiquem só com os nomes e a frase do título |
| 2 + 3 | 0:40 | Uma frase para o problema e os três verbos para a proposta |
| 4 | 1:30 | Tirem a limpeza do texto e o ciclo de correção; mantenham a ordem ML → LLM |
| 5 | 1:30 | Deixem a comparação de modelos e o guia de rotulagem para as perguntas |
| 6, 7 e 8 | 0:20 cada | Uma frase-chave por slide |
| 9 | 0:15 | Só a data da defesa e o agradecimento |

**Total: cerca de 5:10.**

## Checklist antes de apresentar

- [ ] Ensaiar uma vez com cronômetro, cada um no seu trecho.
- [ ] Conferir se o computador da sala tem internet: as fontes vêm do Google Fonts.
- [ ] Navegar com as **setas**. Cuidado para não apertar **E** durante a apresentação: isso liga o modo de edição, e basta apertar E de novo para sair.
- [ ] Quem fala os slides 4 e 5 revisa as perguntas prováveis.
