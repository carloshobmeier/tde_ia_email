# foco.

**Seu e-mail, com espaço para o que importa.**

Assistente pessoal de e-mail com múltiplas contas, classificação supervisionada e modelo de linguagem local. Desenvolvido para um perfil de **Intel i7-1260P, 16 GB de RAM, sem GPU dedicada**, no Windows; também roda no **macOS** (validado em Apple Silicon).

## Abrir neste computador

Execute **`iniciar.bat`** no Windows ou **`iniciar.command`** no macOS. A interface abre em **http://127.0.0.1:8765**.

O iniciador usa o ambiente virtual do projeto, inicia seu próprio Ollama local na porta 11435 quando necessário e abre o navegador. Fechar o terminal encerra o aplicativo. O modelo fica em `.local-data/ollama-models`; não é preciso baixá-lo a cada execução.

Se houver um Foco já aberto, o iniciador abre essa mesma instância. Não execute várias instâncias sobre o mesmo banco.

## Instalar em outro computador

Pré-requisitos: Python **3.11+** (3.12 recomendado), Node.js **22+** com npm e [Ollama](https://ollama.com/download/windows). Reserve aproximadamente 6 GB em disco para ambiente, dependências, modelo e dados iniciais.

1. Execute `instalar.bat`. Ele cria `.venv`, instala as dependências e compila a interface.
2. Execute `preparar_ia.bat`. Ele baixa Qwen3 4B, aproximadamente 2,5 GB, para a pasta do projeto.
3. Execute `iniciar.bat`.
4. Clique em **Explorar demonstração**, importe `.eml` ou configure suas contas.

Instalação e download precisam de internet. Depois disso, leitura das mensagens armazenadas, ML e geração de texto funcionam localmente. A sincronização com Gmail/Outlook continua precisando de internet.

O instalador usa `requirements-lock.txt` com Python 3.12 (validado no Windows e no macOS). Outras versões usam as dependências diretas de `requirements.txt`; elas não receberam a mesma validação de execução desta entrega.

### macOS

Pré-requisitos, via [Homebrew](https://brew.sh):

```bash
brew install python@3.12 node ollama
```

O Ollama também pode vir do [aplicativo oficial](https://ollama.com/download/mac). Os passos são os mesmos, com os arquivos `.command`. Clique duas vezes no Finder ou rode no Terminal, na pasta do projeto:

```bash
./instalar.command
```

```bash
./preparar_ia.command
```

```bash
./iniciar.command
```

- O instalador escolhe Python 3.12 quando disponível (depois 3.13, 3.11).
- Em Apple Silicon (M1 ou mais novo), o Qwen3 usa a GPU via Metal; em Intel, roda em CPU como no Windows.
- Tokens OAuth e o client secret ficam no **Chaves (Keychain)** do macOS. Na primeira leitura o sistema pode pedir permissão.
- Se o macOS bloquear o `.command` por ter vindo da internet, clique com o botão direito → **Abrir**. Se ele abrir sem permissão de execução, rode `chmod +x *.command` uma vez.
- Uma pasta copiada do Windows funciona: o instalador recria o `.venv`. Os dados em `.local-data` são compatíveis.
- Um Ollama que já esteja rodando na porta padrão 11434 não é afetado; o Foco usa sua própria instância na 11435.

## O que já funciona

- Gmail e Outlook/Hotmail/Microsoft 365 com OAuth, várias contas e cursores independentes.
- Sincronização de leitura da **caixa de entrada**, com paginação, detecção de duplicatas e recuperação de cursor expirado.
- Importação de até 100 arquivos `.eml` por lote, 5 MB por arquivo.
- Visão Meu dia, caixa unificada, ações, favoritos, adiados e concluídos.
- Busca em remetente, assunto e corpo; filtros por conta e categoria; paginação no banco.
- Classificação de categoria e prioridade com TF-IDF e modelos supervisionados.
- Comparação entre Regressão Logística, Naive Bayes, SVM linear e classe majoritária.
- Resumos, principal ação, prazo com evidência e rascunhos com Ollama.
- Prazo sugerido precisa de confirmação; prazos confirmados a menos de 24 horas aumentam a prioridade.
- Correções manuais, importação de CSV, retreino e exportação de avaliação e feedback.
- Fila persistente com retomada após interrupção, erros visíveis e nova tentativa.
- Interface clara/escura, fontes locais, atalhos e adaptação para telas menores.

**Não há envio, exclusão nem arquivamento no provedor.** O rascunho é editável, pode ser salvo localmente e copiado para o cliente de e-mail. Leitura, favoritos e conclusão no Foco são estados locais. Se você remover uma mensagem no provedor, a cópia já sincronizada permanece no Foco; remova a conta no aplicativo para apagar suas cópias locais.

Sincronização é manual pelo botão **Sincronizar** e automática imediatamente após conectar a conta. O aplicativo não é um serviço permanente do Windows: precisa estar aberto para processar tarefas.

## Conectar Gmail

O Foco é um aplicativo instalado localmente; ainda assim, o Google exige o cadastro de uma aplicação OAuth.

1. Crie um projeto no Google Cloud e ative a **Gmail API**.
2. Configure a tela de consentimento. Para uso de teste, inclua os endereços que você pretende conectar entre os usuários de teste.
3. Crie um cliente OAuth do tipo **Aplicativo para computador**.
4. Em **Configurações → Conexões de e-mail**, informe o client ID e o client secret. Clique em Salvar alterações.
5. Em **Suas contas**, clique em Conectar Gmail e conclua o consentimento no navegador.

Escopo solicitado: `https://www.googleapis.com/auth/gmail.readonly`. Fluxo com PKCE e callback de loopback `http://127.0.0.1:8765/auth/gmail/callback`.

Esse é um escopo restrito. O aplicativo precisa observar as exigências de teste/verificação do Google para o público que vai utilizá-lo; cadastrar uma aplicação pessoal não equivale a publicá-la para qualquer usuário. Consulte [escopos do Gmail](https://developers.google.com/workspace/gmail/api/auth/scopes) e [OAuth para aplicativos instalados](https://developers.google.com/identity/protocols/oauth2/native-app).

Se o provedor expirar/revogar o consentimento ou o token, o Foco mostra a falha. Reconecte o mesmo endereço; a conta existente é reaproveitada sem duplicar suas mensagens.

## Conectar Outlook / Hotmail / Microsoft 365

1. Registre uma aplicação no Microsoft Entra.
2. Escolha os tipos de conta apropriados. Para contas pessoais e institucionais, selecione a opção que inclui contas Microsoft pessoais e organizações.
3. Em Autenticação, adicione uma plataforma de **aplicativo móvel/desktop** e cadastre exatamente:

   ```text
   http://localhost:8765/auth/outlook/callback
   ```

4. Adicione permissões **delegadas**, não de aplicação: `User.Read` e `Mail.Read`.
5. Copie o **ID do aplicativo (cliente)** para as configurações do Foco. Não é necessário client secret Microsoft neste fluxo público com PKCE.
6. Salve e escolha Conectar Outlook em Suas contas.

O fluxo também solicita `openid profile email offline_access`. Contas institucionais podem exigir consentimento do administrador. Referências: [registro de aplicativo](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app), [fluxo de autorização](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow) e [permissões Graph](https://learn.microsoft.com/en-us/graph/permissions-reference#mailread).

**Validação desta entrega:** conectores testados com respostas HTTP simuladas, incluindo paginação e cursores. A autorização em contas reais precisa ser concluída com suas próprias credenciais OAuth; nenhuma conta pessoal foi acessada durante o desenvolvimento.

## Perfil de IA local

| Opção | Configuração inicial |
|---|---|
| Modelo | `qwen3:4b` |
| Dispositivo | CPU (`num_gpu=0`) |
| Paralelismo | Uma tarefa por vez |
| Threads de inferência | 6 |
| Contexto | 4.096 tokens |
| Limite de geração | 900 tokens |
| Permanência na memória | 5 minutos após a última geração |
| Limite de corpo enviado | 8.000 caracteres; truncamento sinalizado na interface |

O launcher define `OLLAMA_NO_CLOUD=1`; o backend aceita apenas um servidor em loopback e rejeita modelos identificados como remotos. Fontes e ícones são empacotados com a interface. Não existe fallback para API externa.

`preparar_ia.bat` é o caminho recomendado: ele baixa o modelo no armazenamento que o iniciador utiliza. Um `ollama pull` avulso na porta padrão pode baixar em outro diretório. Para acessar a instância do Foco manualmente no PowerShell:

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11435'
ollama list
```

Sem Ollama ou sem modelo instalado, a caixa, busca, organização e ML continuam disponíveis. Os erros de geração aparecem em **Atividade do aplicativo**, onde é possível tentar novamente. O botão “Analisar pendentes” adiciona até 20 mensagens; dependendo da CPU e do tamanho das mensagens, o lote pode levar vários minutos.

O corpo original permanece disponível. A versão atual analisa cada mensagem individualmente, incluindo o texto citado presente nela; não monta automaticamente todo o histórico da conversa. A extração representa **uma ação principal por mensagem**. Datas ambíguas, ações secundárias e informações em anexos exigem revisão do original.

## Dados, treinamento e apresentação

O primeiro treino usa **450 exemplos sintéticos**, organizados em 150 grupos de cenários (30 por categoria, cada um nas três prioridades). Esses exemplos permitem executar o pipeline desde o primeiro uso; **não comprovam qualidade em e-mails pessoais reais**. A demonstração tem 24 mensagens fictícias, com essa origem indicada na interface. São 18 **editoriais**, com rótulos e resumo escritos à mão, que funcionam sem IA e que os modelos nunca alteram. As outras 6 são **ao vivo**: chegam sem rótulo nem resumo, o TF-IDF (com o Qev, se instalado) as classifica e o LLM as analisa na hora. Elas incluem os exemplos de `examples/` e casos difíceis: promoção com "só hoje", golpe pedindo senha com uma instrução maliciosa embutida para a IA, mensalidade da faculdade (financeiro, pelo guia de anotação) e prazos com data explícita.

O treinamento fixa partições por hash do `group_id`: aproximadamente 60% treino, 20% validação e 20% teste. Todas as variações do mesmo cenário ficam juntas. No corpus inicial, a distribuição efetiva é 252/93/105, com todas as classes presentes em cada partição. Remetentes, saudações, frases de contexto e frases de prazo da validação e do teste **nunca aparecem no treino**, então o resultado mede generalização, não memorização de templates. TF-IDF (palavras e n-gramas de caracteres) é ajustado no treino. O melhor classificador de cada tarefa é escolhido por macro-F1 na validação e avaliado no teste, sem usar o teste para escolher o modelo. Resultado atual no teste: macro-F1 de **0,86** para categoria e **0,79** para prioridade (classe majoritária: cerca de 0,05 e 0,19 na validação).

Para treinar com seus dados, importe um CSV UTF-8 na área **Inteligência & dados**:

```csv
text,category,priority,group_id
"Revisar o relatório e responder até hoje às 17h.",trabalho,urgente,conversa-001
"Seguem os materiais da disciplina para consulta.",faculdade,baixa,conversa-002
```

- Categorias: `faculdade`, `trabalho`, `financeiro`, `pessoal`, `promocoes`.
- Prioridades: `urgente`, `normal`, `baixa`.
- `group_id`: identificador da conversa/cenário; mantenha-o consistente em todas as importações.
- Textos idênticos são deduplicados na importação, mantendo a primeira anotação.
- Corrigir na interface atualiza a organização imediatamente. As correções elegíveis entram no treino seguinte; grupos reservados para validação/teste não são promovidos para treino.
- Após retreinar, previsões automáticas são atualizadas, inclusive nas mensagens de demonstração ao vivo. Correções do usuário e mensagens editoriais de demonstração são preservadas.
- Ao importar dados reais, a avaliação passa a incluir o corpus sintético e o importado. A interface identifica esse escopo misto. Para uma conclusão acadêmica sobre generalização real, prepare também uma avaliação independente exclusivamente real.

Veja [docs/AVALIACAO.md](docs/AVALIACAO.md) para o protocolo de anotação, limitações e roteiro de defesa.

### Classificação combinada com o Qev (opcional)

O [Qev 0.8B](https://huggingface.co/twainsk/qev-0.8b) é um modelo neural local de decisão (Apache-2.0): escolhe entre as definições do guia de anotação e devolve probabilidades, sem gerar texto. Com ele instalado, o Foco combina as probabilidades do TF-IDF e do Qev. Sem ele, nada muda.

Instale uma vez com `preparar_qev.bat` (Windows) ou `./preparar_qev.command` (macOS). Precisa de [git](https://git-scm.com) e [uv](https://docs.astral.sh/uv/), internet e cerca de 3 GB. Código e modelos têm versões fixas; o código do runtime foi revisado antes de ser adotado.

Como funciona:

- O `iniciar` sobe o Qev em `127.0.0.1:11436`, sem rede e **sem gravar requisições**. Por padrão o `qev serve` guardaria cada requisição em disco; o Foco desativa isso para que o texto dos e-mails não seja copiado.
- Mensagens recebem o rótulo do TF-IDF na hora. Um refinador em segundo plano consulta o Qev, combina as duas respostas e atualiza a mensagem. Correções do usuário e mensagens de demonstração nunca são alteradas.
- Na primeira vez, o Qev responde os exemplos de validação e teste; depois o modelo é retreinado e a combinação (TF-IDF, Qev, média ponderada ou log-linear, com o peso de cada modelo) é **escolhida na validação**, como os demais modelos. A área **Inteligência & dados** mostra o progresso e o resultado.
- As respostas ficam em cache por texto: retreinar não repete o Qev.
- Os indícios por palavra continuam vindo do TF-IDF.

O Qev carrega PyTorch e cerca de 1,8 GB de pesos e responde em menos de 1 s por e-mail num Mac M-series; na CPU do i7-1260P a latência não foi medida. Detalhes e resultados em [docs/AVALIACAO.md](docs/AVALIACAO.md).

### Alerta de golpe

Em segundo plano, o LLM local verifica as mensagens dos últimos 30 dias, uma por vez e das mais recentes para as mais antigas, procurando sinais de golpe: pedido de senha, código ou dados bancários, ameaça de bloqueio, taxa para liberar prêmio ou encomenda, Pix com pressa, alguém se passando por banco, chefe ou parente.

- Uma mensagem suspeita recebe o selo **Possível golpe** e o motivo. Ela **deixa de ser urgente** (urgência é o que o golpista quer provocar) e sai de **Minhas ações**, para que um boleto falso não vire tarefa.
- O botão **Não é golpe** desfaz o alerta, e **Desfazer** volta atrás. O alerta é automático e pode errar; a decisão é do usuário.
- Mensagens editoriais da demonstração não são verificadas. Uma análise pedida pelo usuário espera no máximo uma verificação.
- O Qev foi avaliado para esta tarefa e não serviu (0 de 10 golpes). O LLM, com o mesmo protocolo, sinalizou 10 de 10 golpes e 1 de 10 mensagens legítimas. Ver [docs/AVALIACAO.md](docs/AVALIACAO.md).

## Privacidade e armazenamento

- `.local-data/foco.sqlite3`: mensagens, metadados, rascunhos, feedback, tarefas e preferências.
- `.local-data/classifier.joblib`: classificadores treinados. Carregue somente artefatos produzidos pelo próprio aplicativo.
- `.local-data/ollama-models`: pesos do LLM.
- `.local-data/qev`: runtime e pesos do Qev opcional. Respostas do Qev ficam no SQLite (`qev_cache`), por hash do texto.
- Cofre de credenciais do sistema: tokens OAuth e client secret Google. Nenhum fallback grava esses segredos em texto puro.
- A interface renderiza conteúdo de e-mail como **texto**, sem executar HTML, scripts ou carregar imagens remotas.
- APIs de alteração exigem token de sessão local; há verificações de origem, Host e contexto de navegação. Serviços escutam apenas em loopback.
- Logs HTTP com URLs de callback ficam desativados para evitar registrar códigos de autorização.

O SQLite **não está criptografado**. A proteção do computador e dos backups continua necessária. Remover uma conta apaga suas mensagens, análises, rascunhos e feedback local; não apaga mensagens no provedor nem apaga exemplos que você tenha importado separadamente para o corpus. Modelos treinados podem refletir dados anteriores; retreine após retirar dados sensíveis de um corpus. O aplicativo não oferece promessa de conformidade legal apenas por ser local.

Para backup consistente, feche o Foco e copie a pasta `.local-data`. Tokens no cofre do sistema não fazem parte dessa cópia; ao migrar de máquina, reconecte as contas. Modelos podem ser baixados novamente. Não publique `.local-data`, CSVs pessoais, tokens ou e-mails reais no repositório.

## Desenvolvimento e testes

```powershell
# Backend, com interface já compilada
$env:FOCO_OLLAMA_URL = 'http://127.0.0.1:11435'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765 --no-access-log

# Testes Python: banco e modelos em diretório temporário
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# Frontend, em outro terminal
cd frontend
npm.cmd run dev

# Compilação e testes no navegador
npm.cmd run build
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

No macOS, os mesmos comandos com `.venv/bin/python`, `npm` e `npx`:

```bash
FOCO_OLLAMA_URL=http://127.0.0.1:11435 .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765 --no-access-log
```

```bash
.venv/bin/python -m unittest discover -s tests -v
```

```bash
cd frontend && npm run build && npx playwright install chromium && npm run test:e2e
```

Os testes de navegador iniciam um backend isolado na porta 8770 e usam `artifacts/e2e-data`. Nunca apontam para a caixa pessoal. Se já houver Chromium do Playwright em outro caminho, `FOCO_BROWSER_PATH` permite selecioná-lo. Os testes de acessibilidade usam injeção controlada do axe em um contexto de teste; a política CSP de produção permanece ativa no aplicativo normal.

Para iniciar também o Ollama durante o desenvolvimento, use `.venv\Scripts\python.exe run.py --no-browser` no lugar do comando direto de uvicorn. Em ambientes com restrição de gerenciamento de processos, o Playwright pode precisar de permissão para encerrar seu próprio servidor de teste no Windows.

Teste opcional com IA real, usando uma mensagem fictícia:

```powershell
$env:FOCO_OLLAMA_URL = 'http://127.0.0.1:11435'
.\.venv\Scripts\python.exe scripts/smoke_ai.py
```

No macOS, com `./iniciar.command` aberto (ele mantém o Ollama da porta 11435):

```bash
FOCO_OLLAMA_URL=http://127.0.0.1:11435 .venv/bin/python scripts/smoke_ai.py
```

Ele salva o resultado em `artifacts/ai-smoke.json`. Consulte [docs/VALIDACAO.md](docs/VALIDACAO.md) para evidências e limites da validação desta entrega.

## Estrutura

```text
backend/       API, SQLite, ML, OAuth, sincronização e worker
frontend/      React, TypeScript, estilos, fontes e testes de navegador
scripts/       instalação, execução do Ollama e teste real de IA
tests/         testes de integração, segurança, parsing e conectores
docs/          avaliação e evidências de validação
experiments/   comparações fora do aplicativo (Qev zero-shot)
.local-data/   dados privados e modelos; ignorados pelo Git
```

IMAP genérico, envio de respostas, análise de anexos, busca semântica e instalador nativo são evoluções futuras. A primeira entrega prioriza leitura e organização pessoal, com decisões revisáveis.
