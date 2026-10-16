import { useEffect, useState } from 'react';
import { ArrowLeft, Check, CheckCheck, Clock3, Copy, ExternalLink, FileText, Lightbulb, LoaderCircle, RefreshCw, Save, Send, ShieldCheck, Sparkles, Star, X } from 'lucide-react';
import { api, patch, post, categoryNames, dateLabel } from './api';
import { Avatar, PriorityBadge, Spinner, useDialog } from './components';
import type { Category, Job, Mail, Priority } from './types';

interface Props { id: string; jobs: Job[]; onClose: () => void; onChange: () => void; notify: (message: string, error?: boolean) => void; }
export default function MailPanel({ id, jobs, onClose, onChange, notify }: Props) {
  const [mail, setMail] = useState<Mail | null>(null), [tab, setTab] = useState<'overview' | 'original'>('overview');
  const [text, setText] = useState(''), [tone, setTone] = useState('cordial'), [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState(''), [dirty, setDirty] = useState(false);
  const ref = useDialog(onClose);
  const active = jobs.find(j => j.target === id && ['queued', 'running'].includes(j.status));
  const completed = jobs.filter(j => j.target === id && j.status === 'done').map(j => j.id).join(',');
  useEffect(() => {
    let cancelled = false;
    api<Mail>(`/messages/${id}`).then(data => { if (!cancelled) { setMail(data); if (!dirty) setText(data.draft || ''); setLoadError(''); } }).catch(e => { if (!cancelled) setLoadError(e.message); });
    return () => { cancelled = true; };
  }, [id, completed]);
  async function update(data: object) {
    try { const result = await patch<Mail>(`/messages/${id}`, data); setMail(result); onChange(); }
    catch (e) { notify((e as Error).message, true); }
  }
  async function run(kind: 'analyze' | 'draft') {
    try { await post(`/messages/${id}/${kind}`, kind === 'draft' ? { tone } : undefined); if (kind === 'draft') setDirty(false); onChange(); notify(kind === 'analyze' ? 'Análise adicionada à fila local.' : 'Preparando seu rascunho no computador.'); }
    catch (e) { notify((e as Error).message, true); }
  }
  async function saveDraft() {
    setSaving(true);
    try { await patch(`/messages/${id}`, { draft: text }); setDirty(false); onChange(); notify('Rascunho salvo neste computador.'); }
    catch (e) { notify((e as Error).message, true); } finally { setSaving(false); }
  }
  async function copy() { try { await navigator.clipboard.writeText(text); notify('Rascunho copiado. Revise antes de enviar.'); } catch { notify('Selecione o rascunho e use Ctrl+C para copiar.', true); } }
  const analysis = mail?.analysis;
  const safeLink = mail?.source_url && /^https:\/\/(mail\.google\.com|outlook\.(office\.com|office365\.com|live\.com))\//.test(mail.source_url) ? mail.source_url : null;
  return <div className="drawer-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}><div className="mail-panel" ref={ref} role="dialog" aria-modal="true" aria-label="Leitura do e-mail">
    <header className="panel-toolbar"><button className="icon-button" onClick={onClose} aria-label="Voltar às mensagens"><ArrowLeft size={20} /></button><span>Um e-mail de cada vez.</span><div className="toolbar-spacer" />{mail && <button className={`icon-button ${mail.starred ? 'is-starred' : ''}`} onClick={() => update({ starred: !mail.starred })} aria-label={mail.starred ? 'Remover favorito' : 'Favoritar'}><Star size={18} fill={mail.starred ? 'currentColor' : 'none'} /></button>}<button className="icon-button" onClick={onClose} aria-label="Fechar e-mail"><X size={20} /></button></header>
    {!mail ? <div className="panel-loading">{loadError ? <p role="alert">{loadError}</p> : <Spinner />}</div> : <>
      <div className="message-heading"><div className="message-kicker"><span className="account-dot" style={{ background: mail.account_color }} />{mail.account_name}<span>·</span>{dateLabel(mail.received_at, true)}</div><h2>{mail.subject}</h2><div className="sender-line"><Avatar name={mail.sender} category={mail.category} /><div><strong>{mail.sender}</strong><span>{mail.sender_email}</span></div><PriorityBadge priority={mail.effective_priority} /></div></div>
      <div className="panel-tabs"><button className={tab === 'overview' ? 'active' : ''} onClick={() => setTab('overview')}><Sparkles size={16} /> Visão inteligente</button><button className={tab === 'original' ? 'active' : ''} onClick={() => setTab('original')}><FileText size={16} /> Mensagem original</button></div>
      <div className="panel-content">
        {mail.demo > 0 && <div className="demo-note"><Lightbulb size={15} /><span>Mensagem fictícia. {mail.analysis_source === 'demo' ? 'Resumo ilustrativo preparado para explorar o aplicativo.' : 'Análise gerada pelo modelo local.'}</span></div>}
        {tab === 'original' ? <><div className="original-meta">Para: {mail.account_email}</div><div className="original-body">{mail.body || '(Mensagem sem conteúdo de texto)'}</div><p className="micro-copy">Conteúdo exibido como texto. Imagens remotas e anexos não são carregados.</p></> : <>
          {active && <div className="processing-banner"><LoaderCircle className="spin" size={18} /><div><strong>{active.status === 'queued' ? 'Na fila de processamento' : active.kind.startsWith('draft') ? 'Escrevendo um rascunho…' : 'Lendo com atenção…'}</strong><span>Você pode continuar usando o Foco.</span></div></div>}
          {analysis ? <section className="ai-summary"><div className="section-kicker"><Sparkles size={15} /> O ESSENCIAL<button className="icon-button" disabled={!!active} onClick={() => run('analyze')} aria-label="Analisar novamente com IA local"><RefreshCw size={14} /></button></div><p className="summary-text">{analysis.summary}</p>{analysis.key_points.length > 0 && <ul className="key-points">{analysis.key_points.map((point, index) => <li key={index}><span />{point}</li>)}</ul>}{analysis.truncated && <p className="inline-warning">A mensagem excede o contexto do modelo; somente o início foi analisado. Confira o original.</p>}{analysis.needs_review && <p className="micro-copy">Há informações que precisam da sua revisão.</p>}</section> : <div className="analysis-empty"><Sparkles size={25} /><h3>Encontre o essencial.</h3><p>Gere um resumo e identifique a próxima ação com a IA do seu computador.</p><button className="button primary" disabled={!!active} onClick={() => run('analyze')}><Sparkles size={16} />Analisar mensagem</button></div>}
          {analysis?.action && <section className={`action-box ${mail.status === 'done' ? 'completed' : ''}`}><div className="section-kicker"><CheckCheck size={16} /> PRÓXIMA AÇÃO</div><h3>{analysis.action}</h3>{analysis.due_at && <div className="due-detail"><Clock3 size={15} /><span>{dateLabel(analysis.due_at, true)}<small>{analysis.due_confirmed ? 'Prazo confirmado por você' : 'Prazo sugerido · confira antes de confirmar'}</small></span></div>}{analysis.due_evidence && <blockquote>“{analysis.due_evidence}”</blockquote>}{analysis.due_at && !analysis.due_confirmed && <button className="text-button" onClick={() => update({ confirm_due: true })}><Check size={14} /> Confirmar este prazo</button>}<div className="action-buttons"><button className="button primary" onClick={() => update({ status: mail.status === 'done' ? 'pending' : 'done', clear_snooze: true })}><Check size={16} />{mail.status === 'done' ? 'Reabrir ação' : 'Marcar como concluída'}</button>{mail.status !== 'done' && <button className="button subtle" onClick={() => update(mail.snoozed ? { clear_snooze: true } : { snoozed_until: new Date(Date.now() + 86400000).toISOString() })}><Clock3 size={16} />{mail.snoozed ? 'Retomar agora' : 'Adiar 24h'}</button>}</div></section>}
          <section className="draft-section"><div className="section-kicker"><Send size={15} /> UMA RESPOSTA, DO SEU JEITO</div><div className="draft-controls"><label>Tom<select value={tone} onChange={e => setTone(e.target.value)}><option value="cordial">Cordial</option><option value="formal">Formal</option><option value="direto">Direto ao ponto</option></select></label><button className="button secondary" disabled={!!active} onClick={() => run('draft')}><Sparkles size={15} />{text ? 'Gerar outro' : 'Criar rascunho'}</button></div>{text || dirty ? <><textarea aria-label="Rascunho de resposta" className="draft-editor" value={text} onChange={e => { setText(e.target.value); setDirty(true); }} rows={7} /><div className="draft-footer"><button className="text-button" disabled={saving || !dirty} onClick={saveDraft}><Save size={14} />{saving ? 'Salvando…' : dirty ? 'Salvar alterações' : 'Salvo localmente'}</button><button className="button secondary small" onClick={copy}><Copy size={14} />Copiar</button></div></> : <p className="micro-copy">A IA prepara. Você revisa e decide o que enviar.</p>}</section>
          <section className="classification"><div className="section-kicker">ORGANIZAÇÃO DA MENSAGEM</div><div className="classification-fields"><label>Categoria<select value={mail.category} onChange={e => update({ category: e.target.value as Category })}>{Object.entries(categoryNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label>Prioridade<select value={mail.priority} onChange={e => update({ priority: e.target.value as Priority })}><option value="urgente">Alta</option><option value="normal">Normal</option><option value="baixa">Baixa</option></select></label></div><p className="micro-copy">{mail.corrected ? 'Classificação corrigida por você. A correção fica disponível para o próximo treino.' : 'Classificação inicial por ML. Corrija quando necessário.'}</p>{mail.signals.length > 0 && <div className="signal-list"><span>Indícios:</span>{mail.signals.map(signal => <span className="signal" key={signal}>{signal}</span>)}</div>}</section>
        </>}
      </div><footer className="panel-bottom"><span><ShieldCheck size={15} />Processamento local</span>{safeLink && <a href={safeLink} target="_blank" rel="noreferrer">Abrir no provedor <ExternalLink size={14} /></a>}{!safeLink && mail.demo > 0 && <span>Ambiente demonstrativo</span>}</footer>
    </>}
  </div></div>;
}
