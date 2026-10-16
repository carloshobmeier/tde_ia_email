"""Corpus sintético de arranque. Não representa desempenho em e-mails reais.

Variações de um mesmo cenário compartilham grupo para não atravessar partições.
"""
import hashlib

SCENARIOS = {
    "faculdade": [
        "entrega do trabalho de inteligência artificial", "inscrição para a monitoria de cálculo",
        "revisão da nota da avaliação de algoritmos", "matrícula nas disciplinas do semestre",
        "apresentação do seminário de banco de dados", "envio do relatório de estágio obrigatório",
        "agendamento da orientação do TCC", "solicitação de histórico escolar na secretaria",
        "atividade complementar da graduação", "acesso ao material de aula no ambiente virtual",
        "reserva do laboratório para o projeto acadêmico", "renovação do empréstimo na biblioteca universitária",
    ],
    "trabalho": [
        "aprovação da proposta comercial do cliente", "revisão do contrato de prestação de serviços",
        "entrega da versão do projeto para a equipe", "agendamento da reunião com o gestor",
        "atualização do relatório de vendas", "validação do orçamento do departamento",
        "retorno ao fornecedor sobre a contratação", "conferência da documentação de integração",
        "correção do incidente no sistema de produção", "planejamento das atividades da sprint",
        "aprovação das férias pelo departamento de RH", "envio da apresentação para a diretoria",
    ],
    "financeiro": [
        "pagamento da fatura do cartão de crédito", "vencimento do boleto do condomínio",
        "conferência do extrato da conta bancária", "renovação do débito automático da conta de luz",
        "pagamento da parcela do financiamento", "confirmação da transferência bancária",
        "regularização da cobrança em atraso", "conferência da nota fiscal da compra",
        "revisão do valor da mensalidade", "pagamento da apólice de seguro",
        "conferência do recibo do aluguel", "confirmação do reembolso no cartão",
    ],
    "pessoal": [
        "confirmação do almoço de família", "agendamento da consulta médica",
        "organização da viagem com amigos", "confirmação de presença no aniversário",
        "retirada da encomenda na portaria", "reserva da hospedagem das férias",
        "agendamento da revisão do carro", "confirmação da aula de música",
        "envio das fotos do encontro de amigos", "organização da mudança de apartamento",
        "agendamento da visita ao veterinário", "confirmação do jantar de sábado",
    ],
    "promocoes": [
        "oferta de tênis com desconto na loja", "cupom de frete grátis no aplicativo",
        "lançamento da coleção de inverno", "newsletter com novidades de tecnologia",
        "oferta exclusiva para assinantes da loja", "campanha de descontos em eletrônicos",
        "seleção semanal de produtos em promoção", "cashback especial no marketplace",
        "catálogo de lançamentos da livraria", "novidades do programa de pontos",
        "liquidação de móveis e decoração", "ofertas de passagens aéreas",
    ],
}


def bootstrap_samples():
    result = []
    for category, scenarios in SCENARIOS.items():
        for index, scenario in enumerate(scenarios):
            if category == "promocoes":
                variants = [
                    ("baixa", f"Última chance! {scenario}. A oferta termina hoje! Publicidade; aproveite se quiser. Descadastre-se aqui."),
                    ("baixa", f"Confira: {scenario}. Nossa seleção da semana para você. Mensagem promocional, nenhuma resposta necessária."),
                    ("normal", f"Sobre a {scenario} que você solicitou: confirme se deseja receber mais informações. Sem prazo definido."),
                ]
            else:
                variants = [
                    ("urgente", f"Ação necessária hoje: {scenario}. Precisamos da sua confirmação até hoje às 17h. O prazo foi antecipado; responda assim que possível."),
                    ("normal", f"Vamos organizar a {scenario}. Por favor, confira os detalhes quando puder e nos dê um retorno durante a próxima semana."),
                    ("baixa", f"Para seu conhecimento: {scenario}. Tudo foi concluído. Segue o registro, nenhuma ação ou resposta é necessária."),
                ]
            for priority, text in variants:
                group = f"bootstrap:{category}:{index}"
                result.append({"id": hashlib.sha256(text.encode()).hexdigest(), "text": text,
                               "category": category, "priority": priority, "group_id": group,
                               "source": "synthetic"})
    return result
