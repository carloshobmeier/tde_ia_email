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

## macOS (Apple Silicon), 09/11/2026

- `./instalar.command` com Python 3.12.8: `requirements-lock.txt` instalado (sem `pywin32-ctypes`), interface compilada.
- Backend: os mesmos 27 testes aprovados. Cofre de credenciais: `keyring.backends.macOS.Keyring`. Após a revisão do classificador (corpus versão 2), a suíte tem 32 testes, todos aprovados: separação de frases entre treino e avaliação, todas as classes em todas as partições, piso de macro-F1 > 0,7, substituição do corpus antigo e indícios em palavras para qualquer modelo selecionado.
- Atualização de uma instalação existente: banco com o corpus antigo (180 exemplos) e modelo sem versão; ao abrir, o Foco substituiu o corpus (450), retreinou e reclassificou as mensagens automaticamente.
- Navegador: os 8 cenários aprovados em três execuções seguidas. O teste de acessibilidade passou a usar `reducedMotion: 'reduce'`, porque o fade-in de 0,35 s fazia o axe medir contraste com opacidade parcial em máquinas rápidas.
- `./iniciar.command`: Ollama próprio localizado pelo Homebrew mesmo com PATH mínimo, servido na porta 11435 e encerrado com Ctrl+C; um Ollama preexistente na 11434 permaneceu intacto.
- Em Apple Silicon, `num_gpu`/`num_thread` não são enviados; o Ollama usa Metal.
- LLM real (`qwen3:4b` Q4_K_M, baixado por `./preparar_ia.command`): 37/37 camadas na GPU Metal, 3,26 GiB (pesos 2,3 GiB, cache 576 MiB). `smoke_ai.py` aprovado: ação identificada, prazo 26/09/2026 17h a partir da data de envio, evidência literal e prazo não confirmado. Tempos: análise 9,6 s com carregamento do modelo e 4,7 s com o modelo carregado; rascunho 2,2–2,6 s.
- Pelo aplicativo: `.eml` importado, classificado (trabalho/urgente, indícios "17h", "por favor") e analisado pela fila.
- **Limitação encontrada:** em `examples/pedido-revisao.eml`, o prazo foi extraído em 3 de 8 execuções (temperatura 0,1); nas outras 5, o modelo copiou a evidência como "às 1:00" em vez de "às 17h". Com temperatura 0, falha sempre nessa mensagem e acerta sempre na do `smoke_ai.py`, ou seja, depende da redação. A validação por evidência literal descartou a data em todas as falhas: nenhum prazo errado chegou à interface, mas o prazo deixou de ser sugerido. Pôr `due_evidence` antes de `due_at` no esquema piorou (0 de 8). Ainda não foi verificado se o mesmo ocorre na CPU do Windows.

## O que permanece dependente do usuário

- Criar/configurar os aplicativos OAuth e consentir o acesso nas suas contas Gmail e Microsoft.
- Rotular um corpus representativo e medir o desempenho em e-mails reais, seguindo `AVALIACAO.md`.
- Conferir desempenho no i7-1260P de destino, incluindo outras aplicações abertas durante o uso.
- Confirmar a turma/data de defesa e preparar o conjunto demonstrativo que será apresentado.

O código, a interface, os scripts de execução e os testes estão entregues. Essas etapas envolvem identidade, dados e hardware que precisam ser validados no contexto pessoal do usuário.

## Qev integrado e demonstração ao vivo, macOS, 09/11/2026

- Backend: 45 testes aprovados. Novos: combinação TF-IDF + Qev escolhida na validação, Qev restrito a loopback, respostas inválidas rejeitadas, servidor sempre com `--no-request-log`, fluxo completo com um Qev falso (cache, retreino, refinamento, correções preservadas), demonstração editorial protegida e ao vivo reclassificada, e as quatro salvaguardas do LLM.
- Navegador: 8 cenários aprovados em duas execuções seguidas. Com a demonstração maior, o axe passou a medir os contadores da barra lateral (números de dois dígitos), que tinham contraste 3,41:1; as cores foram ajustadas para 4,54:1 e 5,16:1.
- Aplicativo real com o Qev (runtime no commit revisado, modelo na revisão fixada): servidor em `127.0.0.1:11436`, nenhuma pasta de gravação de requisições criada. O refinador respondeu os 198 exemplos de validação/teste, o retreino escolheu média ponderada (categoria, 80% TF-IDF) e log-linear (prioridade, 75% TF-IDF), com macro-F1 no teste de 0,935 e 0,846, iguais ao experimento.
- Migração: um banco existente ganhou a coluna `editorial`; as 12 mensagens de demonstração antigas foram marcadas como editoriais e a mensagem importada continuou ao vivo.
- Demonstração ao vivo pelo aplicativo (classificação combinada e análise do LLM pela fila): revisão com prazo de amanhã às 17h correto; materiais sem prazo; promoção "só hoje" como promoções/baixa, sem ação; golpe com o alerta no lugar de "enviar senha"; mensalidade como financeiro, com prazo correto; almoço com prazo na sexta correta. O fuso do último veio em UTC (limitação registrada em AVALIACAO.md).
