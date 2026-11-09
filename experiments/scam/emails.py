"""E-mails fictícios para avaliar alertas de golpe. (é_golpe, assunto, corpo)

DEV escolhe formatos e prompts; EVAL só mede a opção escolhida. Os legítimos de EVAL
*parecem* sensíveis de propósito (senha, código, banco, boleto, Pix): é onde um alerta erra.
"""
DEV = [
    (True, "Seu cartão foi bloqueado", "Identificamos compras suspeitas e bloqueamos seu cartão. Para desbloquear, responda com o número do cartão e a senha."),
    (True, "Herança disponível", "Sou advogado de um parente distante seu. Há uma herança de R$ 300 mil em seu nome; pague R$ 950 de custas para liberar."),
    (True, "Atualize seu token", "Seu token de segurança vence hoje. Instale a nova versão pelo link e confirme sua senha para continuar usando o banco."),
    (True, "IPVA com 60% de desconto", "Pague hoje seu IPVA com 60% de desconto via Pix para a chave do despachante. Oferta válida só até as 18h."),
    (True, "Sua caixa postal vai expirar", "Sua caixa de e-mail será desativada. Confirme seu login e sua senha respondendo esta mensagem para mantê-la ativa."),
    (True, "Me ajuda?", "Oi, sou eu, o Pedro. Estou viajando, perdi a carteira e preciso de R$ 800 por Pix agora. Te devolvo assim que voltar."),
    (False, "Seu extrato mensal", "O extrato de outubro da sua conta corrente está disponível no aplicativo do banco."),
    (False, "Confirme seu cadastro", "Obrigado por se cadastrar na biblioteca digital. Confirme seu e-mail para ativar a conta que você criou hoje."),
    (False, "Lembrete de consulta", "Lembrete: sua consulta odontológica é amanhã às 14h. Em caso de imprevisto, ligue para a clínica."),
    (False, "Nota fiscal da sua compra", "Segue em anexo a nota fiscal da compra realizada ontem na nossa loja. Obrigado pela preferência."),
    (False, "Senha alterada", "A senha da sua conta foi alterada agora há pouco. Se não foi você, entre em contato com o suporte pelo aplicativo oficial."),
    (False, "Reunião remarcada", "Oi! A reunião de alinhamento passou para quinta às 10h, na mesma sala. Até lá!"),
]
EVAL = [
    (True, "Confirme seus dados de acesso", "Detectamos uma tentativa de acesso à sua conta. Para evitar o bloqueio, responda este e-mail com a sua senha."),
    (True, "Fatura atualizada: novo código de barras", "Banco Aur0ra: sua fatura foi atualizada e o boleto anterior foi cancelado. Pague hoje o novo boleto anexo para evitar protesto do seu CPF."),
    (True, "Parabéns, você ganhou!", "Você foi sorteado e ganhou um smartphone! Para receber, pague apenas o frete de R$ 19,90 pelo link nas próximas 2 horas."),
    (True, "Encomenda retida", "Correios: sua encomenda está retida por falta de pagamento da taxa de importação de R$ 7,90. Pague em 24 horas ou ela será devolvida."),
    (True, "Pedido rápido", "Oi, é o Paulo, diretor. Estou em reunião e não posso falar. Preciso que você compre 5 cartões-presente de R$ 200 e me mande os códigos por aqui. É urgente."),
    (True, "Troquei de número", "Oi, mãe! Troquei de número. Preciso pagar uma conta hoje, faz um Pix de R$ 1.500 para esta chave? Depois te explico tudo."),
    (True, "Sua assinatura será suspensa", "Não conseguimos processar seu pagamento. Atualize os dados do seu cartão de crédito em até 2 horas para não perder o acesso à sua conta de streaming."),
    (True, "Vaga home office aprovada", "Parabéns, você foi aprovado para a vaga home office de R$ 5.000 por mês. Para garantir a vaga, pague a taxa de cadastro de R$ 49 ainda hoje."),
    (True, "Restituição disponível", "Receita: você tem uma restituição de R$ 1.284,00 a receber. Informe seus dados bancários e a senha do aplicativo do banco para liberar o depósito."),
    (True, "Validação de acesso", "Para validar seu acesso, responda a este e-mail com o código de 6 dígitos que acabamos de enviar por SMS."),
    (False, "Redefinição de senha", "Você pediu para redefinir sua senha. Se não foi você, ignore este e-mail. O link expira em 1 hora. Nunca pedimos sua senha por e-mail."),
    (False, "Seu código de verificação", "Seu código de verificação é 482913. Não compartilhe este código com ninguém, nem com a nossa equipe."),
    (False, "Boleto do condomínio vence hoje", "O boleto do condomínio, de R$ 620,00, vence hoje. Pagamentos após o vencimento têm multa de 2% e juros. O código de barras está no portal do condômino."),
    (False, "Comprovante do Pix enviado", "Seu Pix de R$ 85,00 para Júlia Mendes foi concluído com sucesso. Guarde este comprovante para consulta. Nenhuma ação é necessária."),
    (False, "Sua fatura está disponível", "Sua fatura de R$ 847,90 está disponível para consulta no aplicativo. Confira os lançamentos antes de realizar o pagamento."),
    (False, "Boleto da mensalidade", "O boleto da mensalidade, no valor de R$ 1.290,00, já está disponível no portal do aluno. Faça o pagamento até o dia 15; após essa data, há multa de 2%."),
    (False, "Salário depositado", "Informamos que seu salário de novembro foi depositado na conta cadastrada. O demonstrativo está no portal do colaborador."),
    (False, "Seu pedido foi enviado", "Seu pedido número 48213 foi enviado e chega em até 5 dias úteis. Acompanhe a entrega pelo aplicativo da loja."),
    (False, "Novo acesso à sua conta", "Detectamos um novo acesso à sua conta pelo Chrome no Mac, em São Paulo. Se foi você, não é preciso fazer nada. Se não foi, altere sua senha pelo aplicativo."),
    (False, "Um último ajuste no projeto de IA", "Para a próxima etapa, incluam a matriz de confusão e expliquem a separação entre treino e teste. Enviem a versão revisada até amanhã às 18h."),
]


def report(name, scores, emails, threshold=0.5):
    """Imprime acertos; scores = P(golpe) ou 0/1."""
    flagged = [s >= threshold for s in scores]
    truth = [e[0] for e in emails]
    tp = sum(f and t for f, t in zip(flagged, truth))
    fp = sum(f and not t for f, t in zip(flagged, truth))
    print(f"{name}: {tp}/{sum(truth)} golpes sinalizados, {fp}/{len(truth) - sum(truth)} legítimos sinalizados por engano")
    for (t, subject, _), f, s in zip(emails, flagged, scores):
        if f != t:
            print(f"   erro: {'golpe não sinalizado' if t else 'legítimo sinalizado'} ({s:.2f}): {subject}")
    return {"scams_flagged": tp, "scams": sum(truth), "false_alarms": fp, "legit": len(truth) - sum(truth)}
