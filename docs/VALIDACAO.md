# Validação da entrega

Verificações executadas no ambiente de desenvolvimento em 25–26/09/2026. O aplicativo foi construído para o perfil i7-1260P/16 GB informado, mas a máquina física utilizada nos testes não foi confirmada como esse processador.

## Compilação

- `npm.cmd run build`: TypeScript e Vite concluíram sem erros.
- JavaScript de produção: aproximadamente 301 kB antes da compressão, 91 kB com gzip.
- Fontes e ícones empacotados localmente.
- Dependências Python isoladas em `.venv`; versões do ambiente validadas em `requirements-lock.txt`.

## Backend — 27 testes aprovados

Comando: `.venv\Scripts\python.exe -m unittest discover -s tests -v`.

Cobertura funcional:

- Importação idempotente, validação de lote, charset desconhecido e data com fuso.
- Conversão segura de HTML para texto, sem scripts nem carregamento de imagens.
- Persistência de rascunho, favorito, adiamento, conclusão e correções de classificação.
- Busca com caracteres especiais e filtros por conta.
- Remoção de contas com cascata; proteção contra remoção durante uma tarefa em andamento.
- Isolamento entre mensagens demonstrativas e importadas.
- Deduplicação e recuperação de tarefas interrompidas.
- Partições de treino/validação/teste sem interseção de grupos.
- Validação atômica de CSV.
- Prazo sugerido não altera urgência antes da confirmação.
- Rejeição de endereço remoto para Ollama e de nomes de modelos de nuvem.
- Formato estruturado compatível com o gerador de gramáticas do Ollama.
- Rejeição de mutações sem token local, origens indevidas e Host não local.
- Gmail: paginação, idempotência e recuperação de histórico expirado.
- Outlook: paginação, delta e bloqueio de links de continuação externos.
- OAuth: PKCE, expiração e consumo de state.
- Falha de sincronização preserva o cursor anterior.

Os provedores externos são simulados com `httpx.MockTransport`. Esses testes não substituem conectar contas reais com o cadastro OAuth do usuário.

## Navegador — 8 cenários aprovados

Playwright/Chromium, backend e banco separados do aplicativo pessoal:

1. Primeiro uso e ativação explícita da demonstração.
2. Busca, leitura, confirmação de prazo, correção de categoria e conclusão preservadas após recarregar.
3. Favoritos, persistência de tema e atalho Ctrl+K.
4. Importação e reimportação de `.eml`, exibição segura do original e ausência de carregamento do rastreador de uma mensagem de teste.
5. Navegação em viewport 390 × 844 sem transbordamento horizontal da tela inicial.
6. Avaliação com origem sintética explícita, troca de tarefa e exportação do relatório.
7. Leitura da interface e mensagem original com solicitações externas bloqueadas no navegador.
8. Auditoria axe da visão principal nos temas claro e escuro, sem violações detectadas nas regras WCAG 2 A/AA e 2.1 AA executadas.

A auditoria automática cobre a tela verificada e não equivale a uma certificação de acessibilidade de todo o produto. O software de segurança da máquina injeta scripts próprios; o teste de independência de rede bloqueia todo tráfego externo para verificar que o aplicativo continua utilizável sem depender dele.

## LLM real em CPU

Modelo: `qwen3:4b`, quantizado Q4_K_M, via Ollama. `num_gpu=0`, seis threads, contexto de 4.096 tokens, uma geração por vez e recursos de nuvem desativados.

O teste `scripts/smoke_ai.py` usou uma mensagem fictícia enviada em **25/09/2026 às 10h, UTC−3**, solicitando revisão **“até amanhã às 17h”**.

- Extraiu uma ação de revisão e a data **26/09/2026 às 17h, UTC−3**.
- Preservou um trecho literal como evidência.
- Manteve o prazo como não confirmado, dependendo de revisão humana.
- Produziu um rascunho em português com marcador de confirmação de disponibilidade.
- A última execução registrada levou aproximadamente **37,6 s para análise** e **15,0 s para rascunho**. Outra execução com o modelo já carregado levou aproximadamente 13,6 s para análise.
- O log do runtime indicou aproximadamente **3,3 GiB** para pesos, cache e grafo do modelo. Isso não mede o consumo total do sistema nem garante a mesma latência em outro computador.

Resultados completos em `artifacts/ai-smoke.json` (artefato local, ignorado pelo Git). Esse cenário comprova a integração funcional com um modelo real; não estabelece fidelidade em todas as mensagens. O rascunho ainda pode sugerir afirmações que precisam ser corrigidas pelo usuário antes de qualquer envio.

## O que permanece dependente do usuário

- Criar/configurar os aplicativos OAuth e consentir o acesso nas suas contas Gmail e Microsoft.
- Rotular um corpus representativo e medir o desempenho em e-mails reais, seguindo `AVALIACAO.md`.
- Conferir desempenho no i7-1260P de destino, incluindo outras aplicações abertas durante o uso.
- Confirmar a turma/data de defesa e preparar o conjunto demonstrativo que será apresentado.

O código, a interface, os scripts de execução e os testes estão entregues. Essas etapas envolvem identidade, dados e hardware que precisam ser validados no contexto pessoal do usuário.
