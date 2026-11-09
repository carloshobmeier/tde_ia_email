"""Corpus sintético de arranque. Não representa desempenho em e-mails reais.

Cada cenário é um grupo: suas variantes nunca atravessam partições.
Para não medir memorização de templates, o treino usa um conjunto de frases
(remetentes, saudações, contexto, frases de prioridade) e validação/teste usam
outro, disjunto. O vocabulário de domínio se repete, como em e-mails reais;
as frases inteiras não.
"""
import hashlib
import random

# Mudar quando o corpus mudar: modelos salvos com outra versão são retreinados.
CORPUS_VERSION = 2


def partition(group):
    """Partição fixa por grupo (~60% treino, 20% validação, 20% teste)."""
    bucket = int(hashlib.sha256(group.encode()).hexdigest()[:8], 16) % 10
    return "test" if bucket < 2 else "validation" if bucket < 4 else "train"


TOPICS = {
    "faculdade": [
        "entrega do trabalho final de Inteligência Artificial", "inscrição para a monitoria de Cálculo II",
        "revisão da nota da prova de Algoritmos", "matrícula nas disciplinas do próximo semestre",
        "apresentação do seminário de Banco de Dados", "relatório do estágio obrigatório supervisionado",
        "orientação do TCC com o professor orientador", "histórico escolar solicitado na secretaria acadêmica",
        "horas de atividades complementares da graduação", "material da aula de Estruturas de Dados",
        "reserva do laboratório de informática para o projeto da disciplina", "renovação do empréstimo na biblioteca universitária",
        "defesa do projeto integrador perante a banca", "lista de exercícios de Estatística",
        "rematrícula e ajuste da grade curricular", "prova substitutiva de Sistemas Operacionais",
        "grupo do TDE de Sistemas de Informação Inteligentes", "frequência mínima nas aulas presenciais",
        "edital de iniciação científica do departamento", "avaliação institucional do curso",
        "aula de reposição de Engenharia de Software", "palestra da semana acadêmica de computação",
        "bolsa de pesquisa do programa de extensão", "artigo para a revista científica do curso",
        "calendário de provas do bimestre", "trancamento de disciplina na coordenação",
        "projeto em grupo de Redes de Computadores", "normas ABNT do trabalho acadêmico",
        "colação de grau e documentos do diploma", "devolutiva do professor sobre o relatório parcial",
    ],
    "trabalho": [
        "aprovação da proposta comercial para o cliente", "revisão do contrato de prestação de serviços",
        "entrega da nova versão do sistema", "reunião de alinhamento com o gestor da área",
        "relatório mensal de vendas", "orçamento anual do departamento",
        "retorno ao fornecedor sobre a contratação", "documentação técnica da integração com o parceiro",
        "incidente no ambiente de produção", "planejamento das tarefas da sprint",
        "solicitação de férias no sistema de RH", "apresentação de resultados para a diretoria",
        "onboarding do novo colaborador do time", "revisão de código do pull request",
        "cronograma de implantação no cliente", "pauta da reunião semanal com o time de produto",
        "avaliação de desempenho do trimestre", "escopo do novo contrato de consultoria",
        "ajuste no backlog após o feedback do cliente", "treinamento obrigatório de segurança da informação",
        "escala de plantão do suporte técnico", "indicadores de desempenho do time comercial",
        "negociação de prazo com o cliente corporativo", "homologação da entrega pelo time de qualidade",
        "apontamento de horas no projeto", "workshop de planejamento estratégico",
        "pedido de compra de notebooks para a equipe", "migração do servidor do cliente para a nuvem",
        "entrevista com candidato para a vaga de analista", "status do projeto para o comitê executivo",
    ],
    "financeiro": [
        "fatura do cartão de crédito", "boleto do condomínio",
        "extrato mensal da conta corrente", "débito automático da conta de energia",
        "parcela do financiamento do carro", "comprovante da transferência via Pix",
        "cobrança em atraso no cartão", "nota fiscal eletrônica da compra on-line",
        "mensalidade da faculdade com vencimento no dia 10", "apólice do seguro residencial",
        "recibo do aluguel do apartamento", "estorno de uma compra na fatura",
        "declaração do imposto de renda", "aumento do limite do cartão de crédito",
        "rendimento da aplicação no CDB", "segunda via da conta de água",
        "tarifa do pacote de serviços bancários", "renegociação da dívida com o banco",
        "IPVA e licenciamento do veículo", "contribuição do plano de previdência",
        "boleto do plano de saúde", "saldo da conta poupança",
        "reembolso de despesas médicas pelo convênio", "cobrança da assinatura de streaming",
        "parcelamento da compra no cartão", "informe de rendimentos para a declaração",
        "lance na assembleia do consórcio", "juros do cheque especial",
        "conta de internet com valor diferente do contratado", "planilha de gastos do mês",
    ],
    "pessoal": [
        "almoço de domingo com a família", "consulta médica de rotina",
        "viagem de fim de semana com os amigos", "festa de aniversário da Júlia",
        "encomenda que chegou na portaria", "hospedagem para as férias de julho",
        "revisão do carro na oficina", "aula de violão de quinta-feira",
        "fotos do encontro da turma do colégio", "mudança para o apartamento novo",
        "consulta da Mel no veterinário", "jantar de sábado na casa da Ana",
        "casamento da prima e lista de presentes", "treino na academia com o personal",
        "churrasco com os vizinhos", "ingressos do show de sábado",
        "visita aos avós no interior", "limpeza no dentista",
        "reunião de condomínio sobre a obra do prédio", "receita do bolo que a tia pediu",
        "bicicleta emprestada para o vizinho", "grupo de corrida no parque",
        "cuidar do cachorro do vizinho no feriado", "chá de bebê da Carla",
        "exame de sangue no laboratório", "passaportes para a viagem em família",
        "conserto da máquina de lavar", "presente de Dia das Mães",
        "trilha com o grupo de amigos", "escola de inglês do meu irmão",
    ],
    "promocoes": [
        "tênis de corrida com 40% de desconto", "cupom de frete grátis no aplicativo",
        "lançamento da coleção de inverno", "newsletter com as novidades de tecnologia",
        "oferta exclusiva para assinantes", "semana de descontos em eletrônicos",
        "seleção de produtos em promoção", "cashback em dobro no marketplace",
        "lançamentos da livraria do mês", "pontos em dobro no programa de fidelidade",
        "liquidação de móveis e decoração", "passagens aéreas com preços especiais",
        "Black Friday antecipada", "curso on-line com matrícula promocional",
        "assinatura anual do aplicativo com desconto", "cardápio especial para delivery",
        "smartphones parcelados sem juros", "kit de skincare com brinde",
        "hotéis em oferta para o feriado", "sorteio para clientes cadastrados",
        "nova linha de cafeteiras", "descontos progressivos no supermercado on-line",
        "queima de estoque de roupas de verão", "webinar gratuito sobre investimentos",
        "cupom de primeira compra no app de comida", "pneus com instalação grátis",
        "novidades da coleção infantil", "frete expresso grátis no fim de semana",
        "clube de vinhos com a primeira caixa promocional", "plano de celular com mais internet",
    ],
}

# Índice 0: frases do treino. Índice 1: frases de validação/teste.
SENDERS = {
    "faculdade": (["Coordenação do Curso de Sistemas de Informação", "Prof.ª Helena Duarte", "Secretaria Acadêmica", "Biblioteca Central"],
                  ["Prof. Marcos Lima, Departamento de Computação", "Central de Atendimento ao Aluno", "Monitoria de Cálculo", "Núcleo de Estágios"]),
    "trabalho": (["Marina Costa, Gerente de Projetos", "Equipe de Produto", "Rafael Almeida, Comercial", "Recursos Humanos"],
                 ["Camila Rodrigues, Head de Operações", "Time de Engenharia", "Diretoria Executiva", "Suporte Técnico"]),
    "financeiro": (["Banco Aurora", "Administradora do Condomínio", "Central do Cartão", "Financeira Horizonte"],
                   ["Cooperativa de Crédito Sul", "Central de Atendimento Bancário", "Seguradora Prisma", "Setor de Cobrança"]),
    "pessoal": (["Regina (mãe)", "Júlia Mendes", "Lucas Ferreira", "Tia Rosa"], ["Vó Lourdes", "Pedro Henrique", "Ana Clara", "Carla Menezes"]),
    "promocoes": (["Casa & Forma", "Clube Vantagens", "TechStore", "Livraria Página"], ["MegaOfertas", "Moda Viva", "App Sabor", "Viagens Sol"]),
}

CONTEXT = {
    "faculdade": (["O enunciado está no ambiente virtual da disciplina.", "A coordenação do curso reforçou as regras no último comunicado.",
                   "Lembrem que isso vale parte da nota do semestre.", "As orientações foram passadas em sala pela professora.",
                   "A secretaria acadêmica atende de segunda a sexta.", "Os detalhes estão no plano de ensino da turma.",
                   "Qualquer dúvida, procure o monitor da disciplina.", "O regulamento da graduação prevê esse procedimento."],
                  ["O professor publicou os critérios no portal do aluno.", "A turma toda recebeu o mesmo aviso da coordenação.",
                   "Isso conta para a média final do curso.", "O documento deve ser enviado pelo sistema acadêmico.",
                   "A banca terá dois professores do departamento.", "As notas parciais já foram lançadas no portal.",
                   "O campus segue o calendário acadêmico publicado.", "Confira o cronograma no ambiente virtual do curso."]),
    "trabalho": (["O cliente pediu uma posição até o fim desta etapa do projeto.", "A equipe já revisou a primeira versão do documento.",
                  "O gestor quer apresentar os números na próxima reunião.", "Isso impacta o cronograma acordado com a diretoria.",
                  "Deixei os arquivos na pasta compartilhada do time.", "O contrato prevê essa entrega nesta fase.",
                  "O time de produto validou o escopo ontem.", "Precisamos manter o fornecedor informado sobre a decisão."],
                 ["A diretoria acompanha esse indicador de perto.", "O material está no drive do projeto, na pasta da equipe.",
                  "Essa demanda veio do cliente na reunião de status.", "O time comercial depende dessa definição para seguir.",
                  "Combinei com a liderança que teríamos uma resposta.", "Isso faz parte das metas do trimestre da empresa.",
                  "Os colegas do suporte também precisam ser avisados.", "O escopo foi aprovado pelo comitê do projeto."]),
    "financeiro": (["O valor será debitado na conta cadastrada.", "O código de barras está no boleto em anexo.",
                    "Consulte o extrato no aplicativo do banco.", "Pagamentos após o vencimento têm multa e juros.",
                    "O comprovante fica disponível no internet banking.", "A fatura detalha cada lançamento do período.",
                    "O valor total já inclui taxas e tarifas.", "Você pode pagar via Pix com a chave informada."],
                   ["O débito aparecerá no seu próximo extrato bancário.", "Há cobrança de juros por dia de atraso.",
                    "O pagamento pode ser feito pelo app ou na lotérica.", "Saldo e limite atualizados estão no aplicativo.",
                    "Guarde o recibo para a sua declaração.", "O vencimento não muda em feriados bancários.",
                    "O valor da parcela foi recalculado com a nova taxa.", "A cobrança será feita no cartão final 4821."]),
    "pessoal": (["Estou com saudade, vai ser bom rever todo mundo!", "A mãe pediu para confirmar quem vai.",
                 "Levo a sobremesa, combinado?", "O pessoal do grupo já está animado.",
                 "Me manda mensagem quando sair de casa.", "Beijos e até logo!",
                 "Vamos aproveitar para colocar a conversa em dia.", "O endereço é o mesmo de sempre."],
                ["A família toda vai estar lá, inclusive os primos.", "Saudade de vocês! Abraço apertado.",
                 "Os amigos perguntaram se você vai levar as crianças.", "Combinei com a vó de passar lá antes.",
                 "Pode levar o cachorro, ele é bem-vindo.", "Fala comigo pelo celular se preferir.",
                 "Estou organizando tudo com carinho, vai ser divertido.", "A gente se vê lá em casa."]),
    "promocoes": (["Use o cupom no carrinho para garantir o desconto.", "Frete grátis para todo o Brasil acima de R$ 99.",
                   "Confira as vitrines com preços especiais.", "Produtos selecionados com até 50% off.",
                   "Baixe o app e ganhe vantagens exclusivas.", "Parcele em até 10x nas compras selecionadas.",
                   "Aproveite as ofertas da loja oficial.", "Novidades fresquinhas chegaram ao site."],
                  ["O desconto é aplicado direto no checkout.", "Membros do clube têm acesso antecipado às ofertas.",
                   "Estoque limitado nas peças em destaque.", "Ganhe pontos a cada compra no site.",
                   "Veja os mais vendidos com preço reduzido.", "Leve 3 e pague 2 em itens participantes.",
                   "Promoção válida no site e no app.", "Cadastre-se para receber ofertas personalizadas."]),
}

# Prioridade = pedido (comum a urgente e normal) + prazo, que carrega a urgência.
# Inclui casos difíceis: "hoje" sem pendência, urgência sem "hoje", negações
# ("nada urgente") e promoções com linguagem de urgência.
REQUESTS = (["Por favor, confirme os dados", "Preciso que você revise o documento", "Envie o arquivo assinado",
             "Responda com a sua decisão", "Confirme sua presença", "Me mande as informações pendentes",
             "Verifique se está tudo correto e responda"],
            ["Peço que você aprove a solicitação", "Mande seu retorno", "Preencha o formulário",
             "Confira os detalhes e confirme", "Envie os documentos solicitados", "Avalie a proposta e me responda",
             "Valide as informações"])
DEADLINES = {
    "urgente": (["até hoje às 17h", "ainda hoje", "nas próximas duas horas", "até o meio-dia de hoje", "imediatamente",
                 "até as 18h de hoje, sem falta", "o quanto antes, pois o prazo vence hoje", "com urgência, ainda nesta manhã"],
                ["até amanhã às 8h, sem falta", "nas próximas horas", "até o fim do dia", "com urgência",
                 "hoje mesmo", "antes das 14h de hoje", "assim que ler esta mensagem, o prazo acaba hoje", "até amanhã cedo"]),
    "normal": (["até a próxima semana", "quando puder", "até o fim do mês", "nos próximos dias, sem pressa",
                "até sexta da semana que vem", "com calma, ao longo do mês", "quando tiver um tempo livre", "até o dia 20"],
               ["até o dia 28", "quando tiver um tempinho", "até o fim da próxima semana", "sem pressa, nas próximas semanas",
                "até o dia 15 do mês que vem", "quando for possível", "no decorrer do mês", "até a reunião do mês que vem"]),
}
FOLLOW_UP = {
    "urgente": (["Caso contrário, a solicitação será cancelada.", "O prazo foi antecipado.", "É o último aviso.", ""],
                ["Depois disso perderemos a vaga.", "Sem isso o processo fica parado.", "Não haverá prorrogação.", ""]),
    "normal": (["Não é nada urgente.", "Fico no aguardo.", "Obrigado desde já.", ""],
               ["Nada urgente, só para organizarmos.", "Qualquer dúvida, me chame.", "Agradeço a atenção.", ""]),
}
NO_ACTION = (["Tudo foi concluído hoje, segue apenas o registro.", "Para seu conhecimento; nenhuma ação é necessária.",
              "Enviamos somente para arquivo, não precisa responder.", "Está tudo certo por aqui, obrigado pela atenção.",
              "Apenas um aviso informativo, sem pendências da sua parte.", "O assunto já foi resolvido; guarde este e-mail se quiser.",
              "A solicitação já foi atendida, não é preciso fazer nada."],
             ["Nada a fazer: é só um resumo do que já aconteceu.", "Compartilho para registro; dispensa resposta.",
              "Esta mensagem é automática e apenas confirma o registro.", "Hoje mesmo encerramos o processo, pode ignorar.",
              "Só para manter você informado; não há prazo envolvido.", "Fica registrado para consulta futura, sem necessidade de retorno.",
              "O processo foi finalizado e não há pendências."])
PROMO = {
    "promo_baixa": (["A oferta termina hoje, aproveite se quiser.", "Confira a nossa seleção da semana para você.",
                     "Mensagem promocional; nenhuma resposta necessária.", "Para deixar de receber, descadastre-se aqui.",
                     "Estoque limitado: garanta já o seu!", "Válido enquanto durarem os estoques."],
                    ["Promoção relâmpago, só nas próximas horas!", "Você recebe este e-mail por ser cliente cadastrado.",
                     "Não perca: descontos imperdíveis até meia-noite.", "Altere suas preferências de e-mail no rodapé.",
                     "Condições especiais por tempo limitado.", "Clique e descubra as ofertas preparadas para você."]),
    "promo_normal": (["Você pediu para ser avisado: confirme se ainda tem interesse.", "Seu cadastro está quase pronto; confirme o e-mail quando puder.",
                      "Sobre o orçamento que você pediu: responda se quiser seguir até o fim do mês."],
                     ["Conforme sua solicitação de orçamento, responda se quiser seguir.", "Recebemos seu pedido de informações; diga se deseja ser contatado.",
                      "Seu pedido de reserva está aguardando; confirme quando puder."]),
}

SUBJECT_PREFIX = {
    "urgente": (["URGENTE: ", "Prazo hoje: ", ""], ["Importante: ", "[Ação necessária] ", ""]),
    "normal": (["", "Re: "], ["", "Pergunta: "]),
    "baixa": (["Registro: ", "", "Para conhecimento: "], ["Informativo: ", "", "Confirmação: "]),
    "promo_baixa": (["Última chance! ", "Novidade: ", ""], ["Só hoje: ", "Oferta: ", ""]),
    "promo_normal": (["", "Seu pedido: "], ["", "Solicitação: "]),
}
FRAMING = (["Assunto: {t}.", "Tema: {t}."], ["Ref.: {t}.", "Em pauta: {t}."])
GREETING = (["Olá,", "Oi, tudo bem?", "Bom dia,"], ["Boa tarde,", "Prezado(a),", "Olá, como vai?"])
CLOSING = (["Abraços,", "Atenciosamente,", "Obrigado,"], ["Até mais,", "Att.,", "Grato(a),"])

VARIANTS = {"promocoes": ["promo_baixa", "promo_baixa", "promo_normal"], "default": ["urgente", "normal", "baixa"]}
LABEL = {"promo_baixa": "baixa", "promo_normal": "normal"}


def priority_sentence(style, pick):
    if style in PROMO:
        return pick(PROMO[style])
    if style == "baixa":
        return pick(NO_ACTION)
    return f"{pick(REQUESTS)} {pick(DEADLINES[style])}. {pick(FOLLOW_UP[style])}".strip()


def compose(category, topic, style, pool, rng):
    pick = lambda options: rng.choice(options[pool])
    subject = pick(SUBJECT_PREFIX[style]) + topic[0].upper() + topic[1:]
    body = " ".join([pick(FRAMING).format(t=topic), pick(CONTEXT[category]), priority_sentence(style, pick)])
    return f"{subject}\n{pick(GREETING)}\n\n{body}\n\n{pick(CLOSING)}\n{pick(SENDERS[category])}"


def bootstrap_samples():
    result = []
    for category, topics in TOPICS.items():
        for index, topic in enumerate(topics):
            group = f"bootstrap:{category}:{index}"
            pool = 0 if partition(group) == "train" else 1
            for variant, style in enumerate(VARIANTS.get(category, VARIANTS["default"])):
                rng = random.Random(int(hashlib.sha256(f"{group}:{variant}".encode()).hexdigest()[:16], 16))
                text = compose(category, topic, style, pool, rng)
                result.append({"id": hashlib.sha256(text.encode()).hexdigest(), "text": text,
                               "category": category, "priority": LABEL.get(style, style), "group_id": group,
                               "source": "synthetic"})
    return result
