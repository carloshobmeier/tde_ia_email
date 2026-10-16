"""Mensagens e análises editoriais fictícias, identificadas na interface."""
import json
from datetime import datetime, timedelta, timezone
from .db import connect, now
from .mail import store_message


def seed_demo():
    stamp = datetime.now(timezone.utc)
    local = stamp.astimezone(timezone(timedelta(hours=-3)))
    tomorrow = (local + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    meeting = local.replace(hour=16, minute=0, second=0, microsecond=0)
    bill = (local + timedelta(days=5)).replace(hour=23, minute=59, second=0, microsecond=0)
    accounts = [
        ("demo-personal", "gmail", "pessoal@exemplo.com", "Pessoal", "#d7836a"),
        ("demo-work", "outlook", "trabalho@exemplo.com", "Trabalho", "#7492c8"),
        ("demo-college", "outlook", "faculdade@exemplo.com", "Faculdade", "#9b87bf"),
    ]
    with connect() as db:
        for account in accounts:
            db.execute("INSERT OR IGNORE INTO accounts(id,provider,email,name,color,demo,last_sync) VALUES (?,?,?,?,?,1,?)", (*account, now()))
    items = [
        ("college", "Prof.ª Ana Beatriz", "ana@universidade.exemplo", "Um último ajuste no projeto de IA", "faculdade", "urgente", 25,
         f"Olá!\n\nGostei da evolução da proposta do grupo. Para a próxima etapa, incluam a matriz de confusão e expliquem a separação entre treino e teste.\n\nEnviem a versão revisada até amanhã às 18h ({tomorrow:%d/%m/%Y}). Depois disso, podemos marcar uma orientação rápida.\n\nAbraços,\nAna Beatriz",
         "A professora pediu a matriz de confusão e a explicação da divisão dos dados na proposta revisada.", "Revisar e enviar a proposta de IA", tomorrow.isoformat(), "até amanhã às 18h", ["Incluir matriz de confusão", "Explicar a separação entre treino e teste"]),
        ("work", "Marina Costa", "marina@estudio.exemplo", "Podemos fechar a proposta hoje?", "trabalho", "urgente", 65,
         f"Oi!\n\nA proposta está na última versão. Você consegue revisar o escopo e me passar seu retorno hoje até as 16h ({meeting:%d/%m/%Y})?\n\nPrecisamos confirmar se as duas rodadas de revisão estão contempladas antes de enviar ao cliente.\n\nObrigada,\nMarina",
         "Marina precisa da sua revisão do escopo antes de encaminhar a proposta ao cliente.", "Revisar o escopo da proposta", meeting.isoformat(), "hoje até as 16h", ["Conferir duas rodadas de revisão", "Retornar para Marina"]),
        ("personal", "Banco Aurora", "fatura@aurora.exemplo", "Sua fatura de setembro está disponível", "financeiro", "normal", 130,
         f"Olá!\n\nSua fatura de R$ 847,90 está disponível para consulta no aplicativo.\nVencimento: {bill:%d/%m/%Y}.\n\nConfira os lançamentos antes de realizar o pagamento. Se você já pagou, desconsidere este aviso.\n\nEquipe Aurora",
         f"Fatura de R$ 847,90 disponível, com vencimento em {bill:%d/%m}. Confira os lançamentos no aplicativo.", "Conferir a fatura do cartão", bill.isoformat(), f"Vencimento: {bill:%d/%m/%Y}", ["Valor: R$ 847,90", "Conferir se o pagamento já foi realizado"]),
        ("work", "Rafael Almeida", "rafael@estudio.exemplo", "Notas da nossa conversa de ontem", "trabalho", "normal", 195,
         "Oi!\n\nOrganizei os pontos da reunião: simplificar o cadastro, revisar a tela inicial e testar a navegação com três pessoas.\n\nQuando tiver um tempo, me diga qual dessas frentes você prefere assumir. Sem pressa para hoje.\n\nValeu!\nRafa",
         "Rafael compartilhou três frentes de trabalho e pede que você escolha uma para assumir.", "Escolher uma frente do projeto", None, None, ["Cadastro", "Tela inicial", "Teste de navegação"]),
        ("college", "Biblioteca Central", "biblioteca@universidade.exemplo", "Seu livro já está esperando por você", "faculdade", "normal", 260,
         "Olá!\n\nO livro Inteligência Artificial: uma abordagem moderna, que você reservou, está disponível no balcão de atendimento. Consulte o horário de funcionamento antes de vir.\n\nBoa leitura!",
         "O livro reservado está disponível para retirada na biblioteca.", "Retirar o livro reservado", None, None, ["Retirada no balcão de atendimento"]),
        ("personal", "Júlia Mendes", "julia@amigos.exemplo", "Café no sábado? ☕", "pessoal", "normal", 330,
         "Oi!\n\nVamos conhecer aquele café novo no sábado? Pensei em ir por volta das 10h. Me avisa se funciona para você e a gente combina.\n\nBeijo,\nJu",
         "Júlia sugeriu um café no sábado às 10h e aguarda sua confirmação.", "Confirmar o café com a Júlia", None, None, ["Sugestão: sábado às 10h", "Local ainda a combinar"]),
        ("personal", "Curadoria Semanal", "leitura@curadoria.exemplo", "Cinco boas ideias para uma semana mais leve", "promocoes", "baixa", 390,
         "Uma pausa para boas ideias.\n\nNesta edição: como cultivar o hábito de leitura, organizar a mesa de trabalho e encontrar tempo para caminhar.\n\nEsta é uma newsletter gratuita. Você pode cancelar sua inscrição a qualquer momento.",
         "Newsletter com dicas de leitura, organização e bem-estar. Nenhuma ação necessária.", None, None, None, ["Leitura opcional"]),
        ("work", "Equipe de Produto", "produto@estudio.exemplo", "A nova versão já está no ar", "trabalho", "baixa", 460,
         "Pessoal,\n\nA versão foi publicada e os testes de verificação passaram. Obrigado pela colaboração de todos nesta entrega!\n\nEste é apenas um informe; nenhuma ação adicional é necessária.",
         "A equipe confirmou a publicação da nova versão. Nenhuma ação pendente.", None, None, None, ["Publicação concluída", "Verificações aprovadas"]),
        ("college", "Coordenação do Curso", "coordenacao@universidade.exemplo", "Materiais do próximo encontro", "faculdade", "normal", 560,
         "Olá, turma!\n\nOs materiais sobre avaliação de modelos já estão disponíveis no ambiente virtual. Leiam o capítulo sobre precisão, recall e F1 antes do próximo encontro. A data está no calendário da disciplina.\n\nAté lá!",
         "A coordenação disponibilizou a leitura sobre precisão, recall e F1 para o próximo encontro.", "Ler o capítulo de avaliação de modelos", None, None, ["Prazo depende do calendário da disciplina"]),
        ("personal", "Casa & Forma", "novidades@casa.exemplo", "Seu cantinho de trabalho, do seu jeito", "promocoes", "baixa", 680,
         "Conheça nossa seleção de luminárias, organizadores e acessórios para sua mesa. Frete grátis em compras selecionadas. Publicidade. Cancele o recebimento quando quiser.",
         "Oferta de acessórios para escritório. Nenhuma obrigação ou resposta necessária.", None, None, None, ["Conteúdo promocional"]),
        ("personal", "Lucas Ferreira", "lucas@amigos.exemplo", "As fotos da nossa viagem", "pessoal", "baixa", 1450,
         "Oi!\n\nFinalmente organizei as fotos do fim de semana. Que viagem boa! Quando a gente se encontrar, mostro o álbum completo.\n\nAbraço,\nLucas",
         "Lucas organizou as fotos da viagem e quer compartilhar o álbum no próximo encontro.", None, None, None, ["Mensagem pessoal, sem solicitação pendente"]),
        ("work", "Camila Rodrigues", "camila@estudio.exemplo", "Uma ideia para o próximo projeto", "trabalho", "normal", 1550,
         "Oi!\n\nPensei em incluir entrevistas com usuários no próximo ciclo. Você poderia avaliar se conseguimos reservar duas manhãs para isso? Ainda não temos datas fechadas.\n\nObrigada!",
         "Camila propõe entrevistas com usuários e pede uma avaliação de disponibilidade.", "Avaliar disponibilidade para entrevistas", None, None, ["Reservar duas manhãs", "Datas ainda não definidas"]),
    ]
    created_count = 0
    for index, item in enumerate(items):
        account, sender, address, subject, category, priority, minutes, body, summary, action, due, evidence, points = item
        message_id, created = store_message("demo-" + account, {
            "remote_id": f"demo-v1-{index}", "thread_id": f"demo-thread-{index}",
            "sender": sender, "sender_email": address, "subject": subject, "body": body,
            "received_at": (stamp - timedelta(minutes=minutes)).isoformat(), "unread": index < 6})
        if created:
            analysis = {"summary": summary, "key_points": points, "action": action, "due_at": due,
                        "due_evidence": evidence, "due_confirmed": False, "needs_review": False, "truncated": False}
            with connect() as db:
                db.execute("UPDATE messages SET category=?,priority=?,analysis=?,analysis_source='demo',analyzed_at=? WHERE id=?",
                           (category, priority, json.dumps(analysis, ensure_ascii=False), now(), message_id))
            created_count += 1
    return {"imported": created_count}
