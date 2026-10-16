# Avaliação e defesa do TDE

## Relação com o enunciado

| Requisito | Evidência implementada |
|---|---|
| ML — 10% | Dois classificadores supervisionados, comparação de algoritmos, validação por grupo, macro-F1 e matriz de confusão. |
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

TF-IDF de palavras e bigramas, até 18 mil features. Modelos candidatos: Regressão Logística com pesos balanceados, Naive Bayes e SVM linear com pesos balanceados; classe majoritária como referência. Treino local sem ajuste de LLM.

Partição determinística por grupo: cerca de 60% treino, 20% validação, 20% teste. A proporção efetiva pode variar, especialmente em bases pequenas. Seleção por macro-F1 na validação; teste permanece fora da seleção. O relatório JSON inclui scores por classe, suporte, matriz de confusão e comparações.

O corpus de partida tem 180 exemplos sintéticos provenientes de 60 cenários. Os templates compartilham estilo; mesmo separados por cenário, os resultados podem ser otimistas. As métricas iniciais devem ser apresentadas como **verificação do pipeline**, não como desempenho comprovado no mundo real.

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

O teste real automatizado em `scripts/smoke_ai.py` verifica apenas um cenário de prazo relativo e geração de rascunho. Isso é evidência funcional, não uma avaliação abrangente da qualidade do LLM.

## Roteiro de demonstração (8–10 minutos)

1. **Problema (1 min):** várias contas e decisões misturadas; apresentar Meu dia.
2. **Entrada (1 min):** mostrar contas e importar uma mensagem `.eml` nova.
3. **ML (2 min):** abrir classificação, corrigir um rótulo, mostrar comparação e matriz de confusão. Explicitar quais dados são sintéticos e quais são reais.
4. **LLM (2 min):** analisar a nova mensagem, conferir evidência de prazo e criar um rascunho. Deixar o modelo carregado antes de apresentar.
5. **Saída e integração (1 min):** confirmar prazo, concluir uma ação, filtrar outra conta e recarregar a página para demonstrar persistência.
6. **Ética e limites (1 min):** mostrar original, revisão humana, ausência de envio automático e incertezas.
7. **Evidência local (1 min):** com dependências/modelo previamente instalados, desconectar a rede e gerar uma análise nova. Conectores precisam de rede; IA local não.

Preparar um conjunto demonstrativo sem dados pessoais e um vídeo de contingência identificado como gravação. Não depender de autorização OAuth ao vivo no dia da defesa.
